

def _planificado(dobras):
    return {'face_referencia': 'F1', 'k_factor': 0.5, 'caixa_mm': {'largura': 100.0, 'altura': 40.0},
            'dobras': [{'raio_interno_mm': 3.0, 'angulo_dobra_graus': 90.0, 'ba_mm': 5.1}] * dobras}


def test_desenvolvimento_lido_de_planificados_quando_falta(tmp_path):
    """Pasta legada (pluvial R04) tem `planificados.json` e não `desenvolvimentos_<REV>.json`: a oficina deriva as
    dobras do planificado pela mesma função do adaptador, e o arquivo de origem fica registrado."""
    entrada = montar_entrada(tmp_path / 'e')
    (entrada / '02_dados' / f'desenvolvimentos_{REV}.json').unlink()
    (entrada / '02_dados' / 'planificados.json').write_text(
        json.dumps({'U': _planificado(2), 'PLACA': _planificado(0)}), encoding='utf-8')
    ent = oficina.ler_entrada(entrada)
    assert ent['desenvolvimentos']['U']['bend_count'] == 2
    assert ent['desenvolvimentos']['PLACA']['bend_count'] == 0
    assert ent['arquivos_entrada']['desenvolvimentos'].name == 'planificados.json'


def test_desenvolvimento_explicito_tem_prioridade_sobre_planificados(tmp_path):
    entrada = montar_entrada(tmp_path / 'e')
    (entrada / '02_dados' / 'planificados.json').write_text(json.dumps({'U': _planificado(5)}), encoding='utf-8')
    assert oficina.ler_entrada(entrada)['desenvolvimentos']['U']['bend_count'] == 2
