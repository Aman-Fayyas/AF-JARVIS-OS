import argparse
import json
from .ipc import events


def main():
    parser = argparse.ArgumentParser(description="AF JARVIS Core client")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("new")
    sub.add_parser("conversations")
    sub.add_parser("facts")
    sub.add_parser("reload")
    chat = sub.add_parser("chat")
    chat.add_argument("prompt")
    chat.add_argument("--conversation")
    chat.add_argument("--route", default="auto", choices=["auto", "local", "advanced_local", "cloud"])
    chat.add_argument("--sensitive", action="store_true")
    probe = sub.add_parser("probe")
    probe.add_argument("id")
    remember = sub.add_parser("remember")
    remember.add_argument("content")
    confirm = sub.add_parser("confirm")
    confirm.add_argument("nonce")
    search = sub.add_parser("search")
    search.add_argument("query")
    args = vars(parser.parse_args())
    args["method"] = args.pop("command")
    for event in events(args):
        if event["type"] == "token":
            print(event["text"], end="", flush=True)
        else:
            print("\n" + json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()
