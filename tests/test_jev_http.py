import json
import unittest
from pathlib import Path
import sys
from urllib.error import HTTPError
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.jev_http import JevHttpClient, JevHttpError, ENDPOINT


class FakeResponse:
    def __init__(self, payload, url=ENDPOINT):
        self.body = json.dumps(payload).encode('utf-8')
        self.url = url
        self.status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def geturl(self): return self.url
    def read(self, _limit): return self.body


def answer(a=.98, b=.02, usage=None):
    return {"model": "typesafe/jev-1.14-20261014", "answers": {"task": {
        "type": "choice", "choice": "a", "probabilities": {"a": a, "b": b},
        "confidence": .97}}, "usage": usage or {}}


class HttpClientTests(unittest.TestCase):
    def test_single_http_post_is_correct_and_metrics_observed(self):
        send = Mock(return_value=FakeResponse(answer(usage={
            'input_tokens': 200, 'output_tokens': 30, 'cost': 0.0000084})))
        result = JevHttpClient('sk-or-synthetic-test', transport=send).classify('Fix Python CI', ['a', 'b'])
        self.assertEqual(result['label'], 'a')
        self.assertEqual(result['execution_status'], 'SUCCESS')
        self.assertEqual(result['confidence'], .98)
        self.assertAlmostEqual(result['margin'], .96)
        self.assertEqual(result['tokens_in'], 200)
        self.assertEqual(result['cost_usd'], 0.0000084)
        self.assertEqual(send.call_count, 1)
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Bearer sk-or-synthetic-test')
        body = json.loads(request.data)
        self.assertEqual(body['model'], 'typesafe/jev-1.14')
        self.assertEqual(body['questions']['task']['type'], 'choice')
        self.assertEqual(set(body['questions']['task']['criteria']), {'a','b'})
        self.assertEqual(body['state']['items']['task'], 'Fix Python CI')
        self.assertEqual(send.call_args.kwargs['timeout'], 30)

    def test_review_keeps_prediction_and_does_not_claim_cost(self):
        result = JevHttpClient('synthetic', transport=lambda *a,**k: FakeResponse(answer(.60, .40))).classify('ambiguous', ['a','b'])
        self.assertEqual(result['label'], 'uncertain')
        self.assertEqual(result['predicted_label'], 'a')
        self.assertEqual(result['execution_status'], 'REVIEW')
        self.assertIsNone(result['cost_usd'])

    def test_invalid_distribution_and_redirect_fail_closed(self):
        for obj in [answer(.99, .99), answer(float('nan'), 0.0)]:
            with self.assertRaises(JevHttpError):
                JevHttpClient('synthetic', transport=lambda *a,**k: FakeResponse(obj)).classify('text', ['a','b'])
        with self.assertRaisesRegex(JevHttpError, 'JEV_REDIRECT_DENIED'):
            JevHttpClient('synthetic', transport=lambda *a,**k: FakeResponse(answer(), 'https://other.test')).classify('text', ['a','b'])

    def test_http_error_has_safe_status_code_and_no_retry(self):
        send = Mock(side_effect=HTTPError(ENDPOINT, 401, 'private diagnostic', {}, None))
        with self.assertRaisesRegex(JevHttpError, 'AUTH_REJECTED'):
            JevHttpClient('synthetic', transport=send).classify('text', ['a','b'])
        self.assertEqual(send.call_count, 1)

    def test_legacy_key_only_with_openrouter_prefix(self):
        c = JevHttpClient.from_environment({'TYPESAFE_API_KEY':'sk-or-synthetic'})
        self.assertEqual(c.model, 'typesafe/jev-1.14')
        for env in ({'TYPESAFE_API_KEY':'ts_private'}, {}, {'OPENROUTER_API_KEY':'ts_wrong'}):
            with self.assertRaises(JevHttpError): JevHttpClient.from_environment(env)

if __name__ == '__main__': unittest.main()
