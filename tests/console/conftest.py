import pytest
import shutil

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

from poetry.config import Config as BaseConfig
from poetry.console import Application as BaseApplication
from poetry.installation.noop_installer import NoopInstaller
from poetry.poetry import Poetry as BasePoetry
from poetry.packages import Locker as BaseLocker
from poetry.repositories import Pool
from poetry.repositories import Repository
from poetry.utils._compat import Path
from poetry.utils.toml_file import TomlFile
from poetry.utils.toml_file import TOMLFile


@pytest.fixture()
def installer():
    return NoopInstaller()


def mock_clone(self, source, dest):
    # Checking source to determine which folder we need to copy
    parts = urlparse.urlparse(source)

    folder = (
        Path(__file__).parent.parent
        / 'fixtures' / 'git'
        / parts.netloc / parts.path.lstrip('/').rstrip('.git')
    )

    shutil.rmtree(str(dest))
    shutil.copytree(str(folder), str(dest))


@pytest.fixture(autouse=True)
def setup(mocker, installer):
    # Set Installer's installer
    p = mocker.patch('poetry.installation.installer.Installer._get_installer')
    p.return_value = installer

    p = mocker.patch('poetry.installation.installer.Installer._get_installed')
    p.return_value = Repository()

    # Patch git module to not actually clone projects
    mocker.patch('poetry.vcs.git.Git.clone', new=mock_clone)
    mocker.patch('poetry.vcs.git.Git.checkout', new=lambda *_: None)
    p = mocker.patch('poetry.vcs.git.Git.rev_parse')
    p.return_value = '9cf87a285a2d3fbb0b9fa621997b3acc3631ed24'

    # Patch provider progress rate to have a consistent
    # dependency resolution output
    p = mocker.patch(
        'poetry.puzzle.provider.Provider.progress_rate',
        new_callable=mocker.PropertyMock
    )
    p.return_value = 3600


class Application(BaseApplication):

    def __init__(self, poetry):
        super(Application, self).__init__()

        self._poetry = poetry

    def reset_poetry(self):
        poetry = self._poetry
        self._poetry = Poetry.create(self._poetry.file.path.parent)
        self._poetry._pool = poetry.pool


class Config(BaseConfig):

    def __init__(self, _):
        self._raw_content = {}
        self._content = TOMLFile([])


class Locker(BaseLocker):

    def __init__(self, lock, local_config):
        self._lock = TomlFile(lock)
        self._local_config = local_config
        self._lock_data = None
        self._content_hash = self._get_content_hash()

    def _write_lock_data(self, data):
        self._lock_data = None


class Poetry(BasePoetry):

    def __init__(self,
                 file,
                 local_config,
                 package,
                 locker
                 ):
        self._file = TomlFile(file)
        self._package = package
        self._local_config = local_config
        self._locker = Locker(locker.lock.path, locker._local_config)
        self._config = Config.create('config.toml')

        # Configure sources
        self._pool = Pool()


@pytest.fixture
def repo():
    return Repository()


@pytest.fixture
def poetry(repo):
    p = Poetry.create(
        Path(__file__).parent.parent / 'fixtures' / 'simple_project'
    )

    with p.file.path.open() as f:
        content = f.read()

    p.pool.remove_repository('pypi')
    p.pool.add_repository(repo)

    yield p

    with p.file.path.open('w') as f:
        f.write(content)


@pytest.fixture
def app(poetry):
    return Application(poetry)
