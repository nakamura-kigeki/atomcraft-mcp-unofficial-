def test_register_all_registers_21_tools(fake_robot):
    from fastmcp import FastMCP
    from atomcraft_mcp.transport import AtomCraftTransport
    from atomcraft_mcp.tools import register_all
    from atomcraft_mcp import config

    mcp = FastMCP(name="test")
    settings = config.load(env={})
    t = AtomCraftTransport(fake_robot, settings)
    names = register_all(mcp, t, settings)
    assert len(names) == 21
    assert sorted(names)[0].startswith("atomcraft_")
