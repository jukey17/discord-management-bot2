import datetime
import os
from os import path
from pathlib import Path
from typing import TypeVar, Generic

from pydantic import BaseModel

T = TypeVar("T")


class RecordList(BaseModel, Generic[T]):
    __root__: list[T]


class LoggingModel(Generic[T]):
    def __init__(self, dir_path: Path, lifetime: datetime.timedelta):
        self._dir_path = dir_path
        self._lifetime = lifetime

    def load_records(self, time: datetime.datetime, *dirs: str) -> list[T]:
        file_path = self._generate_path(time, *dirs)

        if path.exists(file_path):
            record_list = RecordList.parse_file(file_path)
        else:
            record_list = RecordList(__root__=[])

        return record_list.__root__

    def append_record_to_json(self, record: T, time: datetime.datetime, *dirs: str) -> str:
        file_path = self._generate_path(time, *dirs)

        if path.exists(file_path):
            record_list = RecordList.parse_file(file_path)
        else:
            record_list = RecordList(__root__=[])

        record_list.__root__.append(record)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(record_list.json(indent=2))

        return file_path

    def delete_json_if_needed(self, date: datetime.date) -> list[Path]:
        remove_list = []
        for json_path in self._dir_path.glob("**/*.json"):
            filename = path.basename(json_path)
            json_date = datetime.datetime.strptime(filename, "%Y-%m-%d.json").date()
            if date - json_date < self._lifetime:
                continue
            os.remove(json_path)
            remove_list.append(json_path)

        return remove_list

    def _generate_path(self, time: datetime.datetime, *args: str) -> str:
        args_path = path.join(*args)
        dir_path = path.join(self._dir_path, args_path)
        if not path.exists(dir_path):
            os.makedirs(dir_path)

        file_date = time.strftime("%Y-%m-%d")
        return f"{dir_path}/{file_date}.json"
