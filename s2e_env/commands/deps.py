from s2e_env.command import BaseCommand
from s2e_env.commands.init import install_dependencies

class Command(BaseCommand):
    """
    Installs required system packages to build and run S2E.
    """

    help = 'Install required system packages for S2E'

    def handle(self, *args, **options):
        install_dependencies()
