import sys

from oslo.config import cfg
import delato

CONF = cfg.CONF

def main():
    delato.config.parse_args(sys.argv)
    #report = achus.reporter.Report()
    #report.collect()
    #report.generate()


if __name__ == "__main__":
    main()
