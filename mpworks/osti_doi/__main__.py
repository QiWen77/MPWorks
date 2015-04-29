import logging
import argparse
from osti_record import OstiRecord, OstiMongoAdapter

parser = argparse.ArgumentParser()
parser.add_argument("--log", help="show log output", action="store_true")
group = parser.add_mutually_exclusive_group()
group.add_argument("-n", default=0, type=int, help="""number of materials to
                    submit to OSTI. The default (0) collects all materials not
                    yet submitted.""")
group.add_argument('-l', nargs='+', type=int, help="""list of material id's to
                    submit. mp-prefix internally added, i.e. use `-l 4 1986
                   571567`.""")
group.add_argument("--reset", action="store_true", help="""clean all DOIs from
                   materials collection""")
group.add_argument("--info", action="store_true", help="""retrieve materials
                   already having a doi saved in materials collection""")
group.add_argument("--validate", action="store_true", help="""validates all
                   not-yet-validated DOIs in dev matcoll and syncs them to prod
                   matcoll""")
args = parser.parse_args()

loglevel = 'DEBUG' if args.log else 'WARNING'
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('osti')
logger.setLevel(getattr(logging, loglevel))

if args.reset or args.info:
    matad = OstiMongoAdapter()
    if args.reset:
        matad._reset()
    if args.info:
        dois = matad.get_all_dois()
        print dois
        print '{}/{} materials have DOIs.'.format(len(dois), matad.count())
elif args.validate:
    matad = OstiMongoAdapter()
    matad.validate_dois()
    matad.sync_dois()
else:
    # generate records for either n or all (n=0) not-yet-submitted materials 
    # OR generate records for specific materials (submitted or not)
    osti = OstiRecord(l=args.l, n=args.n)
    osti.submit()
