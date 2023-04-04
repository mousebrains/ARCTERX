#
# load credentials
#
import os
import logging
import yaml

def getCredentials(fn:str) -> str:
    fn = os.path.abspath(os.path.expanduser(fn))
    if os.path.isfile(fn):
        try:
            with open(fn, "r") as fp:
                info = yaml.safe_load(fp)
                if "username" in info and "password" in info:
                    return (info["username"], info["password"])
                logging.error("%s is not properly formated", fn)
        except Exception as e:
            logging.warning("Unable to open %s, %s", fn, str(e))

    logging.info("Going to build a fresh credentials file, %s", fn)
    info = {
            "username": input("Enter username: "),
            "password": input("Enter password: "),
            }

    os.makedirs(os.path.dirname(fn), mode=0o700, exist_ok=True)

    with open(fn, "w") as fp:
        yaml.dump(info, fp, indent=4, sort_keys=True)
    return (info["username"], info["password"])
