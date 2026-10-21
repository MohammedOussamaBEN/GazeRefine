"""Entry point used by source launchers and PyInstaller."""
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    from desktop.app import main
    main()
