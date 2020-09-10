#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import os
import sys
import tempfile
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Any, List, NamedTuple, Optional, Tuple

import aiofiles
from idb.cli import ClientCommand
from idb.common.types import FileContainer, FileContainerType, IdbClient


class BundleWithPath(NamedTuple):
    bundle_id: Optional[str]
    path: str

    @classmethod
    def parse(cls, argument: str) -> "BundleWithPath":
        split = argument.split(sep=":", maxsplit=1)
        if len(split) == 1:
            return BundleWithPath(bundle_id=None, path=split[0])
        return BundleWithPath(bundle_id=split[0], path=split[1])


def _extract_bundle_id(args: Namespace) -> FileContainer:
    if args.bundle_id is not None:
        return args.bundle_id
    values = []
    for value in vars(args).values():
        if isinstance(value, List):
            values.extend(value)
        else:
            values.append(value)
    for value in values:
        if not isinstance(value, BundleWithPath):
            continue
        bundle_id = value.bundle_id
        if bundle_id is None:
            continue
        args.bundle_id = bundle_id
    return args.bundle_id


def _convert_args(args: Namespace) -> Tuple[Namespace, FileContainer]:
    def convert_value(value: Any) -> Any:  # pyre-ignore
        if isinstance(value, List):
            return [convert_value(x) for x in value]
        return value.path if isinstance(value, BundleWithPath) else value

    bundle_id = _extract_bundle_id(args)
    args = Namespace(
        **{
            key: convert_value(value)
            for (key, value) in vars(args).items()
            if key != "bundle_id"
        }
    )
    file_container = bundle_id or args.container_type
    return (args, file_container)


class FSCommand(ClientCommand):
    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--bundle-id",
            help="Bundle ID of application. If not provided, the 'root' of the target will be used",
            type=str,
            required=False,
            default=None,
        )
        group.add_argument(
            "--root",
            action="store_const",
            dest="container_type",
            const=FileContainerType.ROOT,
            help="Use the root file container",
        )
        group.add_argument(
            "--media",
            action="store_const",
            dest="container_type",
            const=FileContainerType.MEDIA,
            help="Use the media container",
        )
        group.add_argument(
            "--crashes",
            action="store_const",
            dest="container_type",
            const=FileContainerType.CRASHES,
            help="Use the crashes container",
        )
        group.add_argument(
            "--provisioning-profiles",
            action="store_const",
            dest="container_type",
            const=FileContainerType.PROVISIONING_PROFILES,
            help="Use the provisioning profiles container",
        )
        super().add_parser_arguments(parser)

    @abstractmethod
    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        pass

    async def run_with_client(self, args: Namespace, client: IdbClient) -> None:
        (args, container) = _convert_args(args)
        return await self.run_with_container(
            container=container, args=args, client=client
        )


class FSListCommand(FSCommand):
    @property
    def description(self) -> str:
        return "List a path inside an application's container"

    @property
    def name(self) -> str:
        return "list"

    @property
    def aliases(self) -> List[str]:
        return ["ls"]

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "path", help="Source path", default="./", type=BundleWithPath.parse
        )
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        paths = await client.ls(container=container, path=args.path)
        if args.json:
            print(json.dumps([{"path": item.path} for item in paths]))
        else:
            for item in paths:
                print(item.path)


class FSMkdirCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Make a directory inside an application's container"

    @property
    def name(self) -> str:
        return "mkdir"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        super().add_parser_arguments(parser)
        parser.add_argument(
            "path", help="Path to directory to create", type=BundleWithPath.parse
        )

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        await client.mkdir(container=container, path=args.path)


class FSMoveCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Move a path inside an application's container"

    @property
    def name(self) -> str:
        return "move"

    @property
    def aliases(self) -> List[str]:
        return ["mv"]

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "src",
            help="Source paths relative to Container",
            nargs="+",
            type=BundleWithPath.parse,
        )
        parser.add_argument(
            "dst",
            help="Destination path relative to Container",
            type=BundleWithPath.parse,
        )
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        await client.mv(container=container, src_paths=args.src, dest_path=args.dst)


class FSRemoveCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Remove an item inside a container"

    @property
    def name(self) -> str:
        return "remove"

    @property
    def aliases(self) -> List[str]:
        return ["rm"]

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "path",
            help="Path of item to remove (A directory will be recursively deleted)",
            nargs="+",
            type=BundleWithPath.parse,
        )
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        await client.rm(container=container, paths=args.path)


class FSPushCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Copy file(s) from local machine to target"

    @property
    def name(self) -> str:
        return "push"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "src_paths", help="Path of file(s) to copy to the target", nargs="+"
        )
        parser.add_argument(
            "dest_path",
            help=(
                "Directory relative to the data container of the application\n"
                "to copy the files into. Will be created if non-existent"
            ),
            type=BundleWithPath.parse,
        )
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        return await client.push(
            container=container,
            src_paths=[os.path.abspath(path) for path in args.src_paths],
            dest_path=args.dest_path,
        )


class FSPullCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Copy a file inside an application's container"

    @property
    def name(self) -> str:
        return "pull"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "src", help="Relative Container source path", type=BundleWithPath.parse
        )
        parser.add_argument("dst", help="Local destination path", type=str)
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        await client.pull(
            container=container, src_path=args.src, dest_path=os.path.abspath(args.dst)
        )


class FSShowCommand(FSCommand):
    @property
    def description(self) -> str:
        return "Write the contents of a remote file to stdout"

    @property
    def name(self) -> str:
        return "show"

    def add_parser_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "src", help="Relatve Container source path", type=BundleWithPath.parse
        )
        super().add_parser_arguments(parser)

    async def run_with_container(
        self, container: FileContainer, args: Namespace, client: IdbClient
    ) -> None:
        with tempfile.TemporaryDirectory() as destination_directory:
            # Remove the tempfile so that it can be written to.
            destination_directory = os.path.abspath(destination_directory)
            destination_file = os.path.join(
                destination_directory, os.path.basename(args.src)
            )
            await client.pull(
                container=container, src_path=args.src, dest_path=destination_directory
            )
            async with aiofiles.open(destination_file, "rb") as f:
                data = await f.read()
                sys.stdout.buffer.write(data)
