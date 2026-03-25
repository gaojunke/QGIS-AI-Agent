def classFactory(iface):
    from .plugin import NaturalLanguageQgisAgentPlugin

    return NaturalLanguageQgisAgentPlugin(iface)
