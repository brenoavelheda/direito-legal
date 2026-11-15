from rodar import FERRAMENTAS_PERMITIDAS, _comando


def test_avaliacao_nao_ignora_permissoes():
    argv = _comando("claude", "/direito-legal:consulta [avaliação] x")
    assert "bypassPermissions" not in argv
    assert argv[argv.index("--permission-mode") + 1] == "default"


def test_avaliacao_so_libera_leitura_mcp_e_web():
    argv = _comando("claude", "x")
    permitidas = argv[argv.index("--allowedTools") + 1].split(",")
    assert permitidas == FERRAMENTAS_PERMITIDAS
    assert {"Bash", "Write", "Edit", "NotebookEdit"}.isdisjoint(permitidas)
    assert "mcp__plugin_direito-legal_base-juridica__baixar_lei" in permitidas
    assert "mcp__plugin_direito-legal_base-juridica__configuracao" in permitidas
    proibidas = argv[argv.index("--disallowedTools") + 1].split(",")
    assert {"Bash", "Write", "Edit", "NotebookEdit"} <= set(proibidas)
