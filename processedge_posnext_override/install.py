from processedge_posnext_override.overrides.pos_settings import ensure_posnext_settings_sync


def after_install():
    ensure_posnext_settings_sync()


def after_migrate():
    ensure_posnext_settings_sync()
