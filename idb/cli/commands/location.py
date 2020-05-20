#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from argparse import ArgumentParser, Namespace

from idb.cli import ClientCommand
from idb.common.types import IdbClient


class LocationSetCommand(ClientCommand):
    @property
    def description(self) -> str:
        return "Set a simulator's location"

    @property
    def name(self) -> str:
        return "set-location"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("latitude", help="Latitude to set", type=float)
        parser.add_argument("longitude", help="Longitude to set", type=float)
        super().add_parser_arguments(parser)

    async def run_with_client(self, args: Namespace, client: IdbClient) -> None:
        await client.set_location(args.latitude, args.longitude)
