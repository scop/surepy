"""
surepy.cli
====================================
The cli module of surepy

|license-info|
"""

import asyncio

from datetime import datetime
from functools import wraps
from pathlib import Path
from shutil import copyfile
from surepy.enums import Location
from sys import exit
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

import click

from halo import Halo
from rich import box
from rich.console import Console
from rich.table import Table
from surepy.devices import Flap
from surepy.pet import Pet

from . import (
    TOKEN_ENV,
    SurePetcare,
    __name__ as sp_name,
    __version__ as sp_version,
    natural_time,
)


def coro(f: Any) -> Any:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


token_file = Path("~/.surepy.token").expanduser()
old_token_file = token_file.with_suffix(".old_token")

console = Console(width=100)

CONTEXT_SETTINGS: Dict[str, Any] = dict(help_option_names=["--help"])

version_message = (
    f" [#ffffff]{sp_name}[/] 🐾 [#666666]v[#aaaaaa]{sp_version.replace('.', '[#ff1d5e].[/]')}"
)


def print_header() -> None:
    """print header to terminal"""
    print()
    console.print(version_message, justify="left")
    print()


def token_available(ctx: click.Context) -> Optional[str]:
    if token := ctx.obj.get("token"):
        return str(token)

    console.print("\n  [red bold]no token found![/]\n  checked in:\n")
    console.print("    · [bold]--token[/]")
    console.print(f"    · [bold]{TOKEN_ENV}[/] env var")
    console.print(f"    · [white bold]{token_file}[/]")
    console.print("\n\n  sorry 🐾 [bold]¯\\_(ツ)_/¯[/]\n\n")
    return None


async def json_response(
    data: Dict[Any, Any], ctx: click.Context, sp: Optional[SurePetcare] = None
) -> None:
    if ctx.obj.get("json", False):
        if sp:
            await sp.sac.close_session()

        console.print(data)

        exit(0)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.pass_context
@click.option("--version", default=False, is_flag=True, help=f"show {sp_name} version")
# @click.option("-v", "--verbose", default=False, is_flag=True, help="enable additional output")
# @click.option("-d", "--debug", default=False, is_flag=True, help="enable debug output")
@click.option("-j", "--json", default=False, is_flag=True, help="enable json api response output")
@click.option(
    "-t", "--token", "user_token", default=None, type=str, help="api token", hide_input=True
)
def cli(ctx: click.Context, json: bool, user_token: str, version: bool) -> None:
    """surepy cli 🐾

    https://github.com/benleb/surepy
    """

    ctx.ensure_object(dict)
    # ctx.obj["verbose"] = verbose
    # ctx.obj["debug"] = debug
    ctx.obj["json"] = json
    ctx.obj["token"] = user_token

    # if not json:
    #     print_header()

    if not ctx.invoked_subcommand:

        if version:
            click.echo(version_message)
            exit(0)

        click.echo(ctx.get_help())


@cli.command()
@click.pass_context
@click.option(
    "-u", "--user", required=True, type=str, help="sure petcare api account username (email)"
)
@click.option(
    "-p",
    "--password",
    required=True,
    type=str,
    help="sure petcare api account password",
    hide_input=True,
)
@coro
async def token(ctx: click.Context, user: str, password: str) -> None:
    """get a token"""

    token: Optional[str] = None

    with Halo(text="fetching token", spinner="dots", color="magenta") as spinner:
        sp = SurePetcare(email=user, password=password)

        if token := sp.sac.get_token():

            spinner.succeed("token received!")

            if token_file.exists() and token != token_file.read_text(encoding="utf-8"):
                copyfile(token_file, old_token_file)

            token_file.write_text(token, encoding="utf-8")

        await sp.sac.close_session()

    console.rule(f"[bold]{user}[/] [#ff1d5e]·[/] [bold]Token[/]", style="#ff1d5e")
    console.print(f"[bold]{token}[/]", soft_wrap=True)
    console.rule(style="#ff1d5e")
    print()


@cli.command()
@click.pass_context
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@coro
async def pets(ctx: click.Context, token: Optional[str]) -> None:
    """get pets"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=token)
    await sp.refresh_entities()

    await json_response(sp.pets, ctx)

    table = Table(box=box.MINIMAL)
    table.add_column("Name", style="bold")
    table.add_column("Where", justify="right")
    table.add_column("Change A", justify="right", style="bold")
    table.add_column("Change B", justify="right", style="bold")
    table.add_column("Lunched", justify="right")
    table.add_column("ID 👤 ", justify="right")
    table.add_column("Household 🏡", justify="right")

    # sorted_pets = sorted(pets, key=lambda x: int(pets[x]["household_id"]))

    for pet_id in sp.pets:
        pet: Pet = sp.pets[pet_id]

        change_a = change_b = lunch_time = None

        if pet.feeding:
            change_a = f"{pet.feeding.change[0]}g"
            change_b = f"{pet.feeding.change[1]}g"
            lunch_time = pet.feeding.at if pet.feeding.at else None

        table.add_row(
            str(pet.name),
            str(pet.location),
            f"{change_a}",
            f"{change_b}",
            str(lunch_time),
            str(pet.pet_id),
            str(pet.household_id),
        )

    console.print(table, "", sep="\n")


@cli.command()
@click.pass_context
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@coro
async def devices(ctx: click.Context, token: Optional[str]) -> None:
    """get devices"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=str(token))
    await sp.refresh_entities()

    await json_response(sp.devices, ctx)

    # table = Table(title="[bold][#ff1d5e]·[/] Devices [#ff1d5e]·[/]", box=box.MINIMAL)
    table = Table(box=box.MINIMAL)
    table.add_column("ID", justify="right", style="")
    table.add_column("Household", justify="right", style="")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="")
    table.add_column("Serial", style="")

    # sorted_devices = sorted(devices, key=lambda x: int(devices[x]["household_id"]))

    for device_id in sp.devices:

        device = sp.devices[device_id]

        table.add_row(
            str(device.id),
            str(device.household_id),
            str(device.name),
            str(device.type.name.replace("_", " ").title()),
            str(device.serial) or "-",
        )

    console.print(table, "", sep="\n")


@cli.command()
@click.pass_context
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@click.option("-p", "--pet", "pet_id", required=False, type=int, help="id of the pet")
@click.option(
    "-h", "--household", "household_id", required=True, type=int, help="id of the household"
)
@coro
async def report(
    ctx: click.Context, household_id: int, pet_id: Optional[int] = None, token: Optional[str] = None
) -> None:
    """get pet/household report"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=str(token))
    await sp.refresh_entities()

    json_data = await sp.get_report(pet_id=pet_id, household_id=household_id)

    await json_response(json_data, ctx, sp=sp)

    if data := json_data.get("data"):

        table = Table(box=box.MINIMAL)

        all_keys: List[str] = ["pet", "from", "to", "duration", "entry_device", "exit_device"]

        for key in all_keys:
            table.add_column(str(key))

        for pet in data:

            datapoints: List[Any]
            if (movement := pet["movement"]) and (datapoints := movement["datapoints"]):

                datapoints.sort(key=lambda x: datetime.fromisoformat(x["from"]), reverse=True)

                for datapoint in datapoints[:25]:

                    from_time = datetime.fromisoformat(datapoint["from"])
                    to_time = (
                        datetime.fromisoformat(datapoint["to"])
                        if "active" not in datapoint
                        else None
                    )

                    if "active" in datapoint:
                        datapoint["duration"] = (
                            datetime.now(tz=from_time.tzinfo) - from_time
                        ).total_seconds()

                    entry_device = sp.devices.get(datapoint.get("entry_device_id", 0), None)
                    exit_device = sp.devices.get(datapoint.get("exit_device_id", 0), None)

                    table.add_row(
                        str((sp.pets[pet["pet_id"]]).name),
                        str(from_time.strftime("%d/%m %H:%M")),
                        str(to_time.strftime("%d/%m %H:%M") if to_time else "-"),
                        str(natural_time(datapoint["duration"])),
                        str(entry_device.name if entry_device else "-"),
                        str(exit_device.name if exit_device else "-"),
                    )

        console.print(table, "", sep="\n")


@cli.command()
@click.pass_context
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@coro
async def notification(ctx: click.Context, token: Optional[str] = None) -> None:
    """get notifications"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=str(token))

    json_data = await sp.get_notification() or None

    if json_data:

        await json_response(json_data, ctx)

        if data := json_data.get("data"):

            table = Table(box=box.MINIMAL)

            all_keys: Set[str] = set()
            all_keys.update(*[entry.keys() for entry in data])

            for key in all_keys:
                table.add_column(str(key))

            for entry in data:
                table.add_row(*([str(e) for e in entry.values()]))

            console.print(table, "", sep="\n")


@cli.command()
@click.pass_context
@click.option(
    "-d", "--device", "device_id", required=True, type=int, help="id of the sure petcare device"
)
@click.option(
    "-m",
    "--mode",
    required=True,
    type=click.Choice(["lock", "in", "out", "unlock"]),
    help="locking mode",
)
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@coro
async def locking(
    ctx: click.Context, device_id: int, mode: str, token: Optional[str] = None
) -> None:
    """lock control"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=str(token))

    flap: Optional[Flap]
    if (flap := await sp.flap(flap_id=device_id)) and (type(flap) == Flap):

        lock_control: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None

        if mode == "lock":
            lock_control = flap.lock
            state = "locked"
        elif mode == "in":
            state = "locked in"
        elif mode == "out":
            lock_control = flap.lock_out
            state = "locked out"
        elif mode == "unlock":
            lock_control = flap.unlock
            state = "unlocked"
        else:
            return

        if lock_control:
            with Halo(
                text=f"setting {flap.name} to '{state}'", spinner="dots", color="red"
            ) as spinner:

                if await lock_control(device_id=device_id) and (
                    device := await sp.flap(flap_id=device_id)
                ):
                    spinner.succeed(f"{device.name} set to '{state}' 🐾")
                else:
                    spinner.fail(
                        f"setting to '{state}' probably worked but something else is fishy...!"
                    )

        await sp.sac.close_session()


@cli.command()
@click.pass_context
@click.option("--pet", "pet_id", required=True, type=int, help="id of the pet")
@click.option(
    "--position",
    required=True,
    type=click.Choice(["in", "out"]),
    help="position",
)
@click.option(
    "-t", "--token", required=False, type=str, help="sure petcare api token", hide_input=True
)
@coro
async def position(
    ctx: click.Context, pet_id: int, position: str, token: Optional[str] = None
) -> None:
    """set pet position"""

    token = token if token else ctx.obj.get("token", None)

    sp = SurePetcare(auth_token=str(token))

    pet: Optional[Pet]
    location: Optional[Location]

    if (pet := await sp.pet(pet_id=pet_id)) and (type(pet) == Pet):

        if position == "in":
            location = Location.INSIDE
        elif position == "out":
            location = Location.OUTSIDE
        else:
            return

        if location:
            if await pet.set_position(location):
                console.print(f"{pet.name} set to '{location.name}' 🐾")
            else:
                console.print(
                    f"setting to '{location.name}' probably worked but something else is fishy...!"
                )

        await sp.sac.close_session()


if __name__ == "__main__":
    cli(obj={})
