"""Command line entry point."""
import argparse
import json
import sys

from . import __version__
from .audit import audit


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, '%s: error: %s\n' % (self.prog, message))


def main(argv=None):
    parser = Parser(description='Offline documentation claim auditor')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    command = commands.add_parser('audit', help='Compare documentation with static source evidence')
    command.add_argument('repo', nargs='?', default='.')
    command.add_argument('--json', action='store_true')
    command.add_argument('--verbose', action='store_true')
    command.add_argument('--ignore', action='append', default=[], metavar='PREFIX')
    command.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    try:
        args = parser.parse_args(argv)
        result = audit(args.repo, args.ignore, args.fail_on)
    except SystemExit as error:
        return error.code
    except (OSError, UnicodeError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print('%s %s: %s' % (finding['severity'], finding['rule'], finding['message']))
            for location in finding['locations']:
                print('  %s:%s: %s' % (location['path'], location['line'], location['phrase']))
        if args.verbose:
            for label in ('production_evidence', 'test_evidence'):
                for item in result[label]:
                    print('%s %s:%s: %s' % (label, item['path'], item['line'], item['route']))
    return 2 if result['verdict'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
