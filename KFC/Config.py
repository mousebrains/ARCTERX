#
# Load a YAML file
#
import os.path
import logging
import yaml
import json
import sys

def loadConfig(fn:str, required:tuple[str]=None, prettyPrint:bool=True) -> dict:
    if not os.path.isfile(fn):
        logging.error("%s does not exist!", fn)
        sys.exit(1)

    try:
        with open(fn, "r") as fp:
            info = yaml.safe_load(fp)
        if required is not None:
            for key in required:
                if key not in info:
                    logging.error("Required field, %s, not in %s", key, fn)
                    sys.exit(1)
        if prettyPrint:
            logging.info("%s\n%s", fn, json.dumps(info, indent=2))
        return info
    except:
        logging.exception("Unable to load %s", fn)
        sys.exit(1)
