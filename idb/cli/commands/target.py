#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import os
from argparse import SUPPRESS, ArgumentParser, Namespace
from typing import Union

import idb.common.plugin as plugin
from idb.cli.commands.base import CompanionCommand, ManagementCommand
from idb.common.format import human_format_target_info, json_format_target_info
from idb.common.types import Address, IdbClient, IdbException, IdbManagementClient
from idb.common.udid import is_udid


class DestinationCommandException(Exception):
    pass


class ConnectCommandException(Exception):
    pass


class DisconnectCommandException(Exception):
    pass


def get_destination(args: Namespace) -> Union[Address, str]:
    if is_udid(args.companion):
        return args.companion
    elif args.port and args.companion:
        return Address(host=args.companion, port=args.port)
    else:
        raise DestinationCommandException(
            "provide either a UDID or the host and port of the companion"
        )


class TargetConnectCommand(ManagementCommand):
    @property
    def description(self) -> str:
        return "Connect to a companion"

    @property
    def name(self) -> str:
        return "connect"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "companion",
            help="Host the companion is running on. or the UDID of the target",
            type=str,
        )
        parser.add_argument(
            "port",
            help="Port the companion is running on",
            type=int,
            nargs="?",
            default=None,
        )
        # not used and suppressed. remove after the removal of thrift is deployed everywhere
        parser.add_argument(
            "grpc_port", help=SUPPRESS, type=int, nargs="?", default=None
        )
        super().add_parser_arguments(parser)

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        try:
            destination = get_destination(args=args)
            connect_response = await client.connect(
                destination=destination,
                metadata={
                    key: value
                    for (key, value) in plugin.resolve_metadata(self.logger).items()
                    if isinstance(value, str)
                },
            )
            if connect_response:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "udid": connect_response.udid,
                                "is_local": connect_response.is_local,
                            }
                        )
                    )
                else:
                    print(
                        f"udid: {connect_response.udid} is_local: {connect_response.is_local}"
                    )

        except IdbException:
            raise ConnectCommandException(
                f"""Could not connect to {args.companion:}:{args.port}.
            Make sure both host and port are correct and reachable"""
            )


class TargetDisconnectCommand(ManagementCommand):
    @property
    def description(self) -> str:
        return "Disconnect a companion"

    @property
    def name(self) -> str:
        return "disconnect"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "companion",
            help="Host the companion is running on or the udid of the target",
            type=str,
        )
        parser.add_argument(
            "port",
            help="Port the companion is running on",
            type=int,
            nargs="?",
            default=None,
        )
        super().add_parser_arguments(parser)

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        try:
            destination = get_destination(args=args)
            await client.disconnect(destination=destination)
        except IdbException:
            raise DisconnectCommandException(
                f"Could not disconnect from {args.companion:}:{args.port}"
            )


class TargetDescribeCommand(CompanionCommand):
    @property
    def description(self) -> str:
        return "Describes the Target"

    @property
    def name(self) -> str:
        return "describe"

    async def run_with_client(self, args: Namespace, client: IdbClient) -> None:
        description = await client.describe()
        print(description)


class TargetListCommand(ManagementCommand):
    @property
    def description(self) -> str:
        return "List the connected targets"

    @property
    def name(self) -> str:
        return "list-targets"

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        targets = await client.list_targets()
        if len(targets) == 0:
            if not args.json:
                print("No available targets")
            return

        targets = sorted(targets, key=lambda target: target.name)
        formatter = human_format_target_info
        if args.json:
            formatter = json_format_target_info
        for target in targets:
            print(formatter(target))


class TargetBootCommand(ManagementCommand):
    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--udid",
            help="Udid of target, can also be set with the IDB_UDID env var",
            required=True,
            default=os.environ.get("IDB_UDID"),
        )
        super().add_parser_arguments(parser)

    @property
    def description(self) -> str:
        return "Boots a simulator (only works on mac)"

    @property
    def name(self) -> str:
        return "boot"

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        await client.boot(udid=args.udid)


class TargetShutdownCommand(ManagementCommand):
    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "udid",
            help="Udid of target to shutdown, can also be set with the IDB_UDID env var",
            default=os.environ.get("IDB_UDID"),
        )
        super().add_parser_arguments(parser)

    @property
    def description(self) -> str:
        return "Shuts the simulator down (only works on mac)"

    @property
    def name(self) -> str:
        return "shutdown"

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        await client.shutdown(udid=args.udid)


class TargetEraseCommand(ManagementCommand):
    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "udid",
            help="udid of target to erase, can also be set with the IDB_UDID env var",
            default=os.environ.get("IDB_UDID"),
        )
        super().add_parser_arguments(parser)

    @property
    def description(self) -> str:
        return "Erases the simulator (only works on mac)"

    @property
    def name(self) -> str:
        return "erase"

    async def run_with_client(
        self, args: Namespace, client: IdbManagementClient
    ) -> None:
        await client.erase(udid=args.udid)
