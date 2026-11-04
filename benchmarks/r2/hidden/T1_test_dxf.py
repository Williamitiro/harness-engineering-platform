

def test_ajustar_arcos_retangulo_esparso_vira_quatro_retas():
    """Regressão (26/10/2026): o círculo pelos 4 cantos era aceito como arco, com corda a 3 mm dele."""
    ret = [(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)]
    pecas = ex.ajustar_arcos(ret, 0.02)
    assert [p[0] for p in pecas] == ['LINE'] * 4


def test_ajustar_arcos_quina_viva_de_tres_pontos_nao_vira_arco():
    pecas = ex.ajustar_arcos([(0, 0), (10, 0), (10, 10)], 0.02)
    assert [p[0] for p in pecas] == ['LINE', 'LINE']


def test_ajustar_arcos_quarto_de_circulo_denso_continua_arco():
    import math
    pts = [(10 * math.cos(math.radians(a / 2)), 10 * math.sin(math.radians(a / 2))) for a in range(0, 181)]
    pecas = ex.ajustar_arcos(pts, 0.02)
    assert [p[0] for p in pecas] == ['ARC']
    assert ex.desvio_hausdorff(pts, ex._pontos_pecas(pecas)) <= 0.05


def test_desvio_hausdorff_mede_o_meio_das_cordas():
    ret = [(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)]
    arco_errado = [('ARC', (5, 2.5), 5.59, 0.0, 360.0 - 1e-6)]
    assert ex.desvio_hausdorff(ret, ex._pontos_pecas(arco_errado)) > 1.0
