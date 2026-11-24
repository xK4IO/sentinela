from agent.checagem import checar, numeros_no_texto

EVS = [
    {"id": "E1", "linhas": [[40, 14]]},                       # total_vendas, vendas_disp_creator
    {"id": "E2", "linhas": [[40, 9, 1850.0]]},
    {"id": "E3", "linhas": [["C0388", 3], ["C0511", 2]]},
]


def nums(t):
    return [v for _, v, _, _ in numeros_no_texto(t)]


def test_extrai_formato_brasileiro_e_ignora_ids_datas_hashes():
    assert nums("R$ 1.850,00 em 14 de 40 vendas (35%)") == [1850.0, 14, 40, 35]
    assert nums("C0417 fez login no disp. ***8841 em 20/11/2026 às 10:02, regra R1_AUTOCOMPRA") == []
    assert nums("taxa de 0,35 ou 0.35") == [0.35, 0.35]


def test_numeros_e_razoes_suportados():  # UC01
    assert checar(["14 de 40 vendas (35%) saíram do dispositivo do creator, saque de R$ 1.850,00"],
                  EVS, {"C0417"}) == []


def test_numero_inventado_e_detectado():
    assert checar(["Foram 17 vendas suspeitas"], EVS, set()) == ["número '17'"]


def test_id_inventado_e_detectado():
    assert checar(["Ligado a C0388 e C9999"], EVS, set()) == ["ID 'C9999'"]


def test_constantes_permitidas():
    assert checar(["Nos últimos 30 dias, prazo de 48 horas"], EVS, set()) == []
