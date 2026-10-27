"""Meterless Runtime probe; credentials come only from private storage/stateDir."""
import argparse
import json
import getpass
import sys
from pathlib import Path
from hydroguard.ai.meterless import (RuntimeSettings,MeterlessProvider,auto_detect,parse_connection,MeterlessError)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir",type=Path)
    parser.add_argument("--auto-detect",action="store_true")
    parser.add_argument("--connect-stdin",action="store_true",help="Read a secret connect link from stdin, never argv/logs")
    parser.add_argument("--chat",action="store_true",help="Send a fixed harmless text test on meterless/auto")
    parser.add_argument("--wrong-token-check",action="store_true")
    args=parser.parse_args()
    settings=RuntimeSettings()
    try:
        connection=settings.load()
        if args.state_dir:connection=settings.from_state_dir(args.state_dir,connection.base_url)
        if args.connect_stdin:
            connection=parse_connection(getpass.getpass("Connect link (hidden): ") if sys.stdin.isatty() else sys.stdin.readline());settings.save(connection)
        if args.auto_detect:
            found,status=auto_detect(settings,connection.token)
            if found:connection=found
        else:status=MeterlessProvider(connection).probe()
        output={"provider":"meterless","state":status.state,"requires_token":status.requires_token,"models":status.models}
        if args.wrong_token_check:
            wrong=MeterlessProvider(parse_connection(connection.base_url,"deliberately-invalid-hydroguard-probe")).probe()
            output["wrong_token_state"]=wrong.state
        if args.chat and status.state=="online":
            content=MeterlessProvider(connection).chat("Reply with the word READY.","meterless/auto",max_tokens=16)
            output["chat_returns_string"]=isinstance(content,str)
            output["chat_nonempty"]=bool(content)
        print(json.dumps(output,indent=2))
        return 0 if status.state=="online" else 1
    except MeterlessError as error:
        print(json.dumps({"provider":"meterless","error":str(error)}));return 1


if __name__=="__main__":raise SystemExit(main())
