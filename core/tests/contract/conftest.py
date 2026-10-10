def pytest_addoption(parser):
    parser.addoption("--api", action="store", default=None, help="Base URL of the deployed core API (CoreApiUrl)")
