#!/usr/bin/env python

# ---
# MyMinecraftLauncher - A dependency-free Minecraft launcher in a single Python script.
# ---
# Copyright (c) 2024 5Avian
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ---

import json
import logging
import os
import re
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.request import urlopen
from zipfile import ZipFile

DEBUG = True
APPLICATION_NAME = "MyMinecraftLauncher"
APPLICATION_VERSION = "1.0"

TEMP_DIRECTORY = Path(os.getenv("TEMP")) / APPLICATION_NAME
APPLICATION_DIRECTORY = Path(os.getenv("LOCALAPPDATA")) / APPLICATION_NAME
ASSETS_DIRECTORY = APPLICATION_DIRECTORY / "assets"
ASSET_OBJECTS_DIRECTORY = ASSETS_DIRECTORY / "objects"
ASSET_INDEXES_DIRECTORY = ASSETS_DIRECTORY / "indexes"
PROFILES_DIRECTORY = APPLICATION_DIRECTORY / "profiles"
LIBRARIES_DIRECTORY = APPLICATION_DIRECTORY / "libraries"
EXTRACTED_LIBRARIES_DIRECTORY = LIBRARIES_DIRECTORY / "native"
JAVA_DIRECTORY = APPLICATION_DIRECTORY / "java"
VERSIONS_DIRECTORY = APPLICATION_DIRECTORY / "versions"

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ASSETS_URL = "https://resources.download.minecraft.net"
JRE_DOWNLOAD_URLS = {
    8: "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jre_x64_windows_hotspot_8u392b08.zip",
    17: "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9.1/OpenJDK17U-jre_x64_windows_hotspot_17.0.9_9.zip",
}
JRE_DIRECTORIES = {
    8: JAVA_DIRECTORY / "jdk8u392-b08-jre" / "bin",
    17: JAVA_DIRECTORY / "jdk-17.0.9+9-jre" / "bin",
}
JAVA_EXECUTABLE = "java.exe" if DEBUG else "javaw.exe"


class NewProfileWindow(tk.Toplevel):
    version_label: tk.Label
    versions: tk.Listbox
    name_label: tk.Label
    name: tk.Entry
    create: tk.Button

    def _on_create(self):
        selection = get_selection(self.versions)
        name = self.name.get()
        if selection and not profile_exists(name):
            try:
                create_profile(name, selection)
                self.destroy()
            except Exception as ex:
                delete_profile(name)
                messagebox.showerror(
                    title="An exception occurred", message=str(ex))
                logger.exception(ex)
        else:
            self.create.bell()

    def __init__(self, parent):
        super().__init__(parent)
        self.title(title("New Profile"))
        self.geometry("320x480")

        self.version_label = tk.Label(self, text="Version")
        self.versions = tk.Listbox(self, selectmode=tk.SINGLE)
        self.name_label = tk.Label(self, text="Name")
        self.name = tk.Entry(self)
        self.create = tk.Button(self, text="Create", command=self._on_create)

        for i, version in enumerate(manifest["versions"]):
            self.versions.insert(i, version["id"])
        self.name.insert(0, "My Profile")

        self.create.pack(fill=tk.X, side=tk.BOTTOM)
        self.name.pack(fill=tk.X, side=tk.BOTTOM)
        self.name_label.pack(side=tk.BOTTOM)
        self.version_label.pack(side=tk.TOP)
        self.versions.pack(expand=1, fill=tk.BOTH)


class SetUsernameWindow(tk.Toplevel):
    username_label: tk.Label
    username: tk.Entry
    confirm: tk.Button

    def _on_confirm(self):
        global username
        name = self.username.get().strip()
        if re.match(r"^[A-Za-z0-9_]{1,16}$", name):
            username = name
            application_window.reload()
            self.destroy()
        else:
            self.confirm.bell()

    def __init__(self, parent):
        super().__init__(parent)
        self.title(title("Set Username"))
        self.geometry("320x80")

        self.username_label = tk.Label(self, text="New username")
        self.username = tk.Entry(self)
        self.confirm = tk.Button(self, text="Confirm",
                                 command=self._on_confirm)

        self.username_label.pack()
        self.username.pack(fill=tk.X)
        self.confirm.pack(side=tk.BOTTOM, fill=tk.X)


class ApplicationWindow(tk.Tk):
    menu: tk.Menu
    profiles: tk.Listbox
    profile_context: tk.Menu
    status: tk.Label
    launch: tk.Button
    delete: tk.Button

    def _on_new_profile(self):
        window = NewProfileWindow(self)
        window.grab_set()
        window.focus()

    def _on_set_username(self):
        window = SetUsernameWindow(self)
        window.grab_set()
        window.focus()

    def _on_launch(self, *_):
        selection = get_selection(self.profiles)
        if selection:
            try:
                launch_profile(selection)
            except Exception as ex:
                messagebox.showerror(
                    title="An exception occurred", message=str(ex))
                logger.exception(ex)
        else:
            self.launch.bell()

    def _on_delete(self):
        selection = get_selection(self.profiles)
        if selection:
            try:
                delete_profile(selection)
            except Exception as ex:
                messagebox.showerror(
                    title="An exception occurred", message=str(ex))
                logger.exception(ex)
        else:
            self.launch.bell()

    def _on_profile_context(self, event):
        self.profiles.event_generate(
            "<Button-1>", x=event.x, y=event.y)
        if not get_selection(self.profiles):
            return
        try:
            self.profile_context.tk_popup(event.x_root, event.y_root)
        finally:
            self.profile_context.grab_release()

    def __init__(self):
        super().__init__()
        self.title(title())
        self.geometry("640x480")

        self.menu = tk.Menu(self)
        self.profiles = tk.Listbox(self, selectmode=tk.SINGLE)
        self.profile_context = tk.Menu(self.profiles, tearoff=0)
        self.status = tk.Label(self)
        self.launch = tk.Button(self, text="Launch", command=self._on_launch)
        self.delete = tk.Button(self, text="Delete", command=self._on_delete)

        self.menu.add_command(label="New Profile",
                              command=self._on_new_profile)
        self.menu.add_command(label="Set Username",
                              command=self._on_set_username)
        self.profiles.bind("<Double-Button>", func=self._on_launch)
        self.profiles.bind("<Button-3>", self._on_profile_context)
        self.profile_context.add_command(
            label="Launch", command=self._on_launch)
        self.profile_context.add_command(
            label="Delete", command=self._on_delete)

        self.config(menu=self.menu)
        self.delete.pack(fill=tk.X, side=tk.BOTTOM)
        self.launch.pack(fill=tk.X, side=tk.BOTTOM)
        self.status.pack(side=tk.BOTTOM)
        self.profiles.pack(expand=1, fill=tk.BOTH)
        self.reload()

    def reload(self):
        self.profiles.delete(0, tk.END)
        for i, profile in enumerate(profiles):
            self.profiles.insert(i, profile)
        self.status.config(
            text=f"{len(profiles)} profile(s) loaded - Playing as {username}")


# Returns a formatted title for a window.
def title(text: str | None = None) -> str:
    return f"{text} - {APPLICATION_NAME}" if text else APPLICATION_NAME


# Returns the selection of a listbox with a select mode of `tk.SINGLE`.
def get_selection(listbox: tk.Listbox) -> str | None:
    selection = listbox.curselection()
    return None if not selection or len(selection) < 1 else listbox.get(selection[0])


# Formats a profile or version name to prevent path or argument injection.
def format_name(name: str) -> str:
    name = (
        name.strip()
        .replace("/", "_").replace("\\", "_")
        .replace('"', "_").replace("'", "_")
    )
    return "__" if name == ".." else name


# Returns if this system adheres to the provided rules.
def allowed_by_rules(rules: list[dict]) -> bool:
    allowed = False
    for rule in rules:
        if rule["action"] == "allow":
            if "os" in rule and rule["os"]["name"] == "windows":
                return True
            elif "os" not in rule:
                allowed = True
        elif rule["action"] == "disallow":
            if "os" in rule and rule["os"]["name"] == "windows":
                return False
            elif "os" not in rule:
                allowed = False
    return allowed


# Returns a list of URLs to download relevent libraries given any number of library objects.
def get_library_urls(*args) -> list[str]:
    result = []
    for library in args:
        if "rules" in library and not allowed_by_rules(library["rules"]):
            continue
        if (
            "classifiers" in library["downloads"]
            and "natives-windows" in library["downloads"]["classifiers"]
        ):
            result.append(library["downloads"]
                          ["classifiers"]["natives-windows"]["url"])
        if "artifact" in library["downloads"]:
            result.append(library["downloads"]["artifact"]["url"])
    return result


# Downloads or loads the version.json file.
def get_version_json(id: str) -> dict:
    version_json_path = VERSIONS_DIRECTORY / f"{id}.json"
    if version_json_path.exists():
        with version_json_path.open("r") as file:
            version_json = json.load(file)
    else:
        version_url = next(
            filter(lambda v: v["id"] == id, manifest["versions"]))["url"]
        logger.info(f"Downloading version.json from {version_url}")
        with urlopen(version_url) as res:
            version_json = json.load(res)
        with version_json_path.open("w") as file:
            json.dump(version_json, file)
    return version_json


# Downloads Java for the given version, which should be either 8 or 17.
def download_java(version: int):
    if JRE_DIRECTORIES[version].exists():
        return
    logger.info(f"Downloading Java from {JRE_DOWNLOAD_URLS[version]}")
    zip_path = TEMP_DIRECTORY / \
        f'{JRE_DOWNLOAD_URLS[version].split("/")[-1]}.zip'
    with urlopen(JRE_DOWNLOAD_URLS[version]) as res:
        with zip_path.open("wb") as file:
            file.write(res.read())
    with ZipFile(zip_path, "r") as zipfile:
        zipfile.extractall(JAVA_DIRECTORY)
    zip_path.unlink()


# Downloads the asset index and asset objects for the given version object.
def download_assets(version_json: dict):
    index_path: Path = ASSET_INDEXES_DIRECTORY / \
        (version_json["assetIndex"]["id"] + ".json")
    if index_path.exists():
        with index_path.open("r") as file:
            asset_index = json.load(file)
    else:
        asset_index_url = version_json["assetIndex"]["url"]
        with urlopen(asset_index_url) as res:
            asset_index = json.load(res)
        with open(index_path, "w") as file:
            json.dump(asset_index, file)

    for key, value in asset_index["objects"].items():
        hash = value["hash"]
        short_hash = hash[:2]
        os.makedirs(ASSET_OBJECTS_DIRECTORY / short_hash, exist_ok=True)
        path: Path = ASSET_OBJECTS_DIRECTORY / short_hash / hash
        if path.exists():
            continue
        url = ASSETS_URL + "/" + short_hash + "/" + hash
        logger.info(f"Downloading asset '{key}' from {url}")
        with urlopen(url) as res:
            with path.open("wb") as file:
                file.write(res.read())


# Downloads (and extracts) all libraries necessary to run the given version object.
def download_libraries(version_json: dict):
    for url in get_library_urls(*version_json["libraries"]):
        path = LIBRARIES_DIRECTORY / url.split("/")[-1]
        if path.exists():
            continue
        logger.info(f"Downloading library from {url}")
        with urlopen(url) as res:
            with path.open("wb") as file:
                file.write(res.read())

    directory: Path = EXTRACTED_LIBRARIES_DIRECTORY / version_json["id"]
    directory.mkdir(exist_ok=True)
    for library in version_json["libraries"]:
        if "extract" not in library:
            continue
        for url in get_library_urls(library):
            logger.info(f"Extracting library downloaded from {url}")
            path = LIBRARIES_DIRECTORY / url.split("/")[-1]
            with ZipFile(path, "r") as zipfile:
                zipfile.extractall(directory)


# Downloads the client and all dependencies for the given version object.
def download_version(version_json: dict):
    id = version_json["id"]
    client_path = VERSIONS_DIRECTORY / f"{id}.jar"
    if not client_path.exists():
        client_url = version_json["downloads"]["client"]["url"]
        logger.info(f"Downloading client from {client_url}")
        with urlopen(client_url) as res:
            with client_path.open("wb") as file:
                file.write(res.read())

    download_java(version_json["javaVersion"]["majorVersion"])
    download_libraries(version_json)
    download_assets(version_json)


# Creates a new profile and synchronizes state with the application.
def create_profile(name: str, version_id: str):
    name = format_name(name)
    (PROFILES_DIRECTORY / name / ".minecraft").mkdir(parents=True)
    with (PROFILES_DIRECTORY / name / ".VERSION").open("w") as file:
        file.write(version_id)
    version_json = get_version_json(version_id)
    download_version(version_json)
    link_legacy_assets(name, version_json)
    profiles.append(name)
    application_window.reload()


# Returns if a profile already exists.
def profile_exists(name: str) -> bool:
    return format_name(name) in profiles


# Deletes an existing profile and synchronizes state with the application.
def delete_profile(name: str):
    name = format_name(name)
    shutil.rmtree(PROFILES_DIRECTORY / name)
    if name in profiles:
        profiles.remove(name)
        application_window.reload()


# Creates links to the asset objects for legacy Minecraft versions.
def link_legacy_assets(profile_name: str, version_json: dict):
    profile_name = format_name(profile_name)
    asset_index_id = version_json["assetIndex"]["id"]
    if asset_index_id not in ["legacy", "pre-1.6"]:
        return
    with (ASSET_INDEXES_DIRECTORY / f"{asset_index_id}.json").open("r") as file:
        asset_index = json.load(file)
    legacy_dir: Path = PROFILES_DIRECTORY / \
        profile_name / ".minecraft" / "resources"
    legacy_dir.mkdir(exist_ok=True)

    for file_name, asset in asset_index["objects"].items():
        link: Path = legacy_dir / file_name
        if link.exists():
            continue
        hash = asset["hash"]
        short_hash = hash[:2]
        Path(os.path.dirname(link)).mkdir(parents=True, exist_ok=True)
        os.link(ASSET_OBJECTS_DIRECTORY / short_hash / hash, link)


# Formats JavaScript template literal-styled format strings using the given kwargs.
def format_template(string: str, **kwargs) -> str:
    result = ""
    iterator = iter(string)
    for char in iterator:
        if char != "$":
            result += char
            continue
        char = next(iterator)
        if char != "{":
            result += "$" + char
            continue
        key = ""
        for char in iterator:
            if char == "}":
                break
            key += char
        if char != "}":
            raise Exception("Format should be terminated.")
        result += str(kwargs[key])
    return result


# Launches an existing profile and closes the launcher.
def launch_profile(name: str):
    name = format_name(name)
    with (PROFILES_DIRECTORY / name / ".VERSION").open("r") as file:
        version_id = file.read()
    with (VERSIONS_DIRECTORY / f"{version_id}.json").open("r") as file:
        version_json = json.load(file)
    java_version = version_json["javaVersion"]["majorVersion"]
    java_path = JRE_DIRECTORIES[java_version] / JAVA_EXECUTABLE
    classpath = [
        str(LIBRARIES_DIRECTORY / url.split("/")[-1])
        for url in get_library_urls(*version_json["libraries"])
    ]
    classpath.append(str(VERSIONS_DIRECTORY / f"{version_id}.jar"))
    working_dir = PROFILES_DIRECTORY / name / ".minecraft"

    args = [
        str(java_path),
        f'-Djava.library.path={EXTRACTED_LIBRARIES_DIRECTORY / version_id}',
        f'-Dminecraft.launcher.brand={APPLICATION_NAME}',
        f'-Dminecraft.launcher.version={APPLICATION_VERSION}',
        "-cp",
        ";".join(classpath),
        version_json["mainClass"],
    ]
    game_args: list[str] = (
        version_json["minecraftArguments"].split()
        if "minecraftArguments" in version_json
        else [arg for arg in version_json["arguments"]["game"] if isinstance(arg, str)]
    )
    format_values = {
        "auth_player_name": username,
        "auth_session": "",
        "auth_access_token": "",
        "auth_uuid": "00000000-0000-0000-0000-000000000000",
        "auth_xuid": "",
        "version_name": version_id,
        "version_type": "",
        "game_directory": working_dir,
        "game_assets": working_dir / "resources",
        "assets_root": ASSETS_DIRECTORY,
        "assets_index_name": version_json["assetIndex"]["id"],
        "user_properties": "{}",
        "user_type": "",
        "clientid": "",
    }
    args.extend(format_template(arg, **format_values) for arg in game_args)
    for arg in args:
        logger.info(f"Argument: {arg}")
    application_window.destroy()
    subprocess.call(args, cwd=working_dir)


logger: logging.Logger
manifest: dict
profiles: list[str]
username: str
application_window: ApplicationWindow

if __name__ == "__main__":
    for directory in [
        TEMP_DIRECTORY,
        APPLICATION_DIRECTORY,
        ASSETS_DIRECTORY,
        ASSET_OBJECTS_DIRECTORY,
        ASSET_INDEXES_DIRECTORY,
        PROFILES_DIRECTORY,
        LIBRARIES_DIRECTORY,
        EXTRACTED_LIBRARIES_DIRECTORY,
        JAVA_DIRECTORY,
        VERSIONS_DIRECTORY,
    ]:
        directory.mkdir(exist_ok=True)

    logging.basicConfig()
    logging.root.setLevel(logging.DEBUG if DEBUG else logging.WARNING)
    logger = logging.getLogger(APPLICATION_NAME)
    with urlopen(MANIFEST_URL) as res:
        manifest = json.load(res)
    profiles = os.listdir(PROFILES_DIRECTORY)
    username = "Player"
    application_window = ApplicationWindow()
    logger.info("Finished startup")
    application_window.mainloop()
