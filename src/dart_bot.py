from discord import Client, Message, Embed, utils, TextChannel, File
from torf import Torrent
from qbittorrent import Client as QBClient
from requests import get, Response
from json import load
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

"""
A ghetto script to to ghetto things.
"""

# TODO: write documentation
# TODO: add some "proper" logging
# TODO: default to disabled torrenting when it's impossible to connect to the qbittorrent web api

CONFIG: Dict[str, Any] = dict()
CLIENT: Client = Client()
QBCLIENT: QBClient


def start_seeding(tp: str, fp: str) -> None:
    with open(tp, "rb") as torrent_file:
        QBCLIENT.download_from_file(torrent_file, savepath=fp)

    print("  Seeding the torrent...")


def create_torrent(fp: str) -> str:
    """
    Not documented yet.
    """
    create_at: Any = Path(CONFIG["torrent"]["createAt"]).resolve()

    # Get the file name.
    t_name: str = fp.split("\\")[-1].split(".zip")[0]

    # Append the paths and create a (hopefully) unique file name.
    t_path: Any = create_at / f"{t_name}.torrent"

    t: Torrent = Torrent(fp, trackers=CONFIG["torrent"]["trackers"])
    t.generate()
    t.write(t_path)

    print(f"  -> Created torrent file: {t_path}")

    return str(t_path)


def download_file(url: str) -> Tuple[bool, str]:
    """
    Download the file at the given url and save it in a folder.
    """
    dl_to: Any = Path(CONFIG["repository"]["downloadTo"]).resolve()

    print("url", url)

    filename: str = url.split("/")[-1].split(".zip")[0]

    if CONFIG["repository"]["devBranchName"] in filename:
        filename = f"[unstable]_{filename}" 
    elif CONFIG["repository"]["masterBranchName"] in filename:
        filename = f"[stable]_{filename}" 
    elif not CONFIG["repository"]["devBranchName"] in filename and not CONFIG["repository"]["masterBranchName"] in filename:
        filename = f"[release]_{filename}"

    dt: str = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    filepath: Any = dl_to / f"{filename}_{dt}.zip"

    response: Response = get(url)

    success: bool = False

    try:
        with open(str(filepath), "wb") as f:
            f.write(response.content)

        success = True

        print(f"  -> Downloaded repo archive to: {filepath}")
    except Exception as identifier:
        print(f"  -> Failed to download.")
        print(identifier)

    return success, str(filepath)


def is_valid_message(message: Message) -> bool:
    print(f"New message from: {message.author} (id:{message.author.id})")

    if len(message.embeds) <= 0:
        print("  -> Not a valid message.")
        return False  # Message has no embed content, end it there.

    dev_branch: str = CONFIG["repository"]["devBranchName"]
    embed: Dict[Any, Any] = message.embeds[0].to_dict()

    print(not message.author.id in CONFIG["discord"]["listenTo"]["hookId"])
    print(not message.channel.id in CONFIG["discord"]["listenTo"]["channels"])
    print((f":{dev_branch}" in embed["title"] and CONFIG["repository"]["onlyMaster"]))

    if (
        not message.author.id in CONFIG["discord"]["listenTo"]["hookId"]
        or not message.channel.id in CONFIG["discord"]["listenTo"]["channels"]
        or (f":{dev_branch}" in embed["title"] and CONFIG["repository"]["onlyMaster"])
    ):
        print("  -> Not a valid message.")
        return False
    else:
        print("  -> Valid message.")
        return True


def get_file_url(repo_url: str, text: str) -> str:
    dev_branch: str = CONFIG["repository"]["devBranchName"]
    master_branch: str = CONFIG["repository"]["masterBranchName"]

    print("text :", text)
    print("lower cased: ", text.lower())

    url: str = repo_url

    if not repo_url.endswith("/"):
        url += "/"  # from "http://repo.github.com" to "http://repo.github.com/"

    if not repo_url.endswith("archive/"):
        url += "archive/"  # from "http://repo.github.com/" to "http://repo.github.com/archive/"

    if "new release" in text.lower():
        # remove the backslash before some chars
        tag: str = text.split("New release published: ")[-1].replace("\\", "")

        url += f"{tag}.zip"
    elif "new commit" in text.lower():
        # Adds the final part of the url to the file.
        if f":{dev_branch}" in text:
            url += f"{dev_branch}.zip"
        elif f":{master_branch}" in text:
            url += f"{master_branch}.zip"

    print("release url: ", url)

    return url


@CLIENT.event
async def on_message(message: Message) -> None:
    print("================")
    if not is_valid_message(message):
        return  # Invalid message, ignores it.

    output_channel: TextChannel = CLIENT.get_channel(
        CONFIG["discord"]["outputChannelId"]
    )

    url: str = get_file_url(
        CONFIG["repository"]["url"], message.embeds[0].to_dict()["title"]
    )

    dl_response: Tuple[bool, str] = download_file(url)  # success and filepath

    if not dl_response[0]:
        # Notify end-users on Discord that the download failed.
        await output_channel.send(
            "Something went wrong with the download...\nYou might want to contact an admin."
        )
    else:
        # Notify end-users on Discord that the download succeeded.

        if CONFIG["torrent"]["enabled"]:
            torrentpath: str = create_torrent(dl_response[1])

            start_seeding(torrentpath, dl_response[1])

            await output_channel.send(
                content="New version is available via P2P", file=File(torrentpath)
            )
        else:
            await output_channel.send(
                "Downloaded the new update successfully.\nWaiting for the messiah to torrent it..."
            )


def load_config() -> None:
    global CONFIG

    fp = Path(__file__).parent.resolve()

    try:
        with open(f"{fp}\\config.json") as config_file:
            CONFIG = load(config_file)
    except FileNotFoundError as identifier:
        print("Uh oh... You messed up.")
        print(identifier)
        exit()


def main() -> None:
    load_config()

    if CONFIG["torrent"]["enabled"]:
        global QBCLIENT

        QBCLIENT = QBClient(CONFIG["torrent"]["webUrl"])
        QBCLIENT.login(CONFIG["torrent"]["login"], CONFIG["torrent"]["password"])

    print("Running...")
    CLIENT.run(CONFIG["discord"]["token"])


if __name__ == "__main__":
    main()
