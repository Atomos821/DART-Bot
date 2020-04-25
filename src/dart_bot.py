from discord import Client, Message, Embed, utils, TextChannel, File
from torf import Torrent
from qbittorrent import Client as QBClient
from requests import get, Response
from json import load
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# TODO: write documentation
# TODO: some "proper" logging
# TODO: start torrenting

CONFIG: Dict[str, Any] = dict()
CLIENT: Client = Client()
QBCLIENT: QBClient


def start_seeding(tp: str, fp: str) -> None:
    print("tp:", tp)
    print("fp:", fp)

    with open(tp, "rb") as torrent_file:
        QBCLIENT.download_from_file(torrent_file, savepath=fp)


def create_torrent(fp: str) -> str:
    """
    Not documented yet.
    """

    create_at: Any = Path(CONFIG["torrent"]["createAt"]).resolve()

    # Get the file name.
    t_name: str = fp.split("\\")[-1].split(".zip")[0]

    # Append the paths and create a (hopefully) unique file name.
    t_path: Any = create_at / f"[unstable]_{t_name}.torrent"

    t: Torrent = Torrent(fp, trackers=CONFIG["torrent"]["trackers"])
    t.generate()
    t.write(t_path)

    return str(t_path)


def download_file(url: str) -> Tuple[bool, str]:
    """
    Download the file at the given url and save it in a folder.
    """

    dl_to: Any = Path(CONFIG["repository"]["downloadTo"]).resolve()

    filename: str = url.split("/")[-1].split(".zip")[0]

    dt: str = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    filepath: Any = dl_to / f"{filename}_{dt}.zip"

    response: Response = get(url)

    success: bool = False

    try:
        with open(str(filepath), "wb") as f:
            f.write(response.content)

        success = True
    except Exception as identifier:
        print(identifier)

    return success, str(filepath)


def get_repo_archive_url(repo_url: str) -> str:
    fixed_url: str = repo_url

    if not repo_url.endswith("/"):
        fixed_url += "/"
        print("was missing /")

    if not repo_url.endswith("archive/"):
        fixed_url += "archive/"
        print("was missing archive/")

    return fixed_url


def is_valid_message(message: Message) -> bool:
    # Doing some boolean checks here.
    # I like my ifs like how I like my books: Easy to read.
    valid_user: bool = str(message.author) in CONFIG["discord"]["listenTo"]["users"]
    valid_chan: bool = message.channel.name in CONFIG["discord"]["listenTo"]["channels"]
    author_is_self: bool = message.author == CLIENT.user
    only_master: bool = CONFIG["repository"]["onlyMaster"]

    dev_branch: str = CONFIG["repository"]["devBranchName"]

    # Message has no embed content, will cause error if not checked first.
    if len(message.embeds) <= 0:
        return False

    # It's supposed to have only one embed.
    msg_embed: Dict[Any, Any] = message.embeds[0].to_dict()

    if (
        author_is_self
        or not valid_user
        or not valid_chan
        or (f":{dev_branch}" in msg_embed["title"] and only_master)
    ):
        return False
    else:
        return True


@CLIENT.event
async def on_message(message: Message) -> None:
    if not is_valid_message(message):
        return  # Ignore message.

    dev_branch: str = CONFIG["repository"]["devBranchName"]
    master_branch: str = CONFIG["repository"]["masterBranchName"]
    output_channel_id: int = CONFIG["discord"]["outputChannelId"]
    url: str = get_repo_archive_url(CONFIG["repository"]["url"])

    output_channel: TextChannel = CLIENT.get_channel(output_channel_id)
    msg_embed: Dict[Any, Any] = message.embeds[0].to_dict()

    if "new release" in msg_embed["title"]:
        pass  # TODO: Do something if it's a release.

    elif "new commit" in msg_embed["title"]:

        # Appends the archive url with the correct zip file.
        if f":{dev_branch}" in msg_embed["title"]:
            url += f"{dev_branch}.zip"
        elif f":{master_branch}" in msg_embed["title"]:
            url += f"{master_branch}.zip"

        filepath: str
        success: bool
        msg: str

        success, filepath = download_file(url)

        if not success:
            # Shitty logs to the console.
            print("Could not write to file:", filepath)

            # Notify end users on Discord.
            msg = "Something went wrong with the download...\nYou might want to contact an admin."
            await output_channel.send(msg)

            # Leaves the function quietly.
            return
        else:
            print("Downloaded file successfully.", filepath)

            msg = "Downloaded the new update successfully.\nCreating torrent..."
            await output_channel.send(msg)

            torrentpath: str = create_torrent(filepath)

            start_seeding(torrentpath, filepath)

            await output_channel.send(
                content="New version is available via P2P", file=File(torrentpath)
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
    global QBCLIENT

    load_config()

    QBCLIENT = QBClient(CONFIG["torrent"]["webUrl"])
    QBCLIENT.login(CONFIG["torrent"]["login"], CONFIG["torrent"]["password"])

    CLIENT.run(CONFIG["discord"]["token"])


if __name__ == "__main__":
    main()
