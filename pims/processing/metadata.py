"""Parser to convert BP metadata to dictionary"""

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, List

from bigpicture_metadata_interface.model import (
    Attributes,
    AttributesObject,
    BaseObject,
    BiologicalBeing,
    Code,
    CodeAttributes,
    DACContact,
    Dataset,
    Sample,
    Stain,
    Statement,
    Study,
)

BP_MODEL = (
    AttributesObject,
    BaseObject,
    Code,
    DACContact,
    Sample,
    Stain,
    Statement,
)


class BPMetadataParser:
    """Parse BP metadata"""

    def __init__(
        self,
        studies: List[Study],
        beings: List[BiologicalBeing],
        datasets: List[Dataset],
    ) -> None:
        self.studies = studies
        self.beings = beings
        self.datasets = datasets

        self.filters = {
            "image": None,
            "slide": None,
            "obs": None,
            "being": None,
        }
        self.parsed = {}

        self.parser = {
            "any": self._parse_any,
            dict: self._parse_dict,
            list: self._parse_list,
        }

    def _parse_any(self, anything: Any, prefix: str) -> None:
        """Parse default case

        Attributes
        ----------
        anything: Any
            The class to parse
        prefix: str
            The prefix key
        """

        if isinstance(anything, BP_MODEL):
            self.parse_dataclass(anything, prefix)
        elif isinstance(anything, Enum):
            self._parse_primitive(anything.value, prefix)
        elif isinstance(anything, (Attributes, CodeAttributes)):
            item = list(anything.values())
            self.parser.get(list)(item, prefix)
        else:
            self._parse_primitive(anything, prefix)

    def _parse_primitive(self, primitive: Any, prefix: str) -> None:
        """Parse primitive type

        Attributes
        ----------
        primitive: Any
            The class to parse
        prefix: str
            The prefix key
        """

        self.parsed[prefix] = primitive

        # Filters
        substring = f"{self.filters['image']}.slide.alias"
        if self.filters["image"] and substring in prefix:
            self.filters["slide"] = self.parsed[prefix]

        substring = f"slides.{self.filters['slide']}.id"
        if self.filters["slide"] and substring in prefix:
            if "Observation_" in prefix:
                start = prefix.find("Observation_")
                self.filters["obs"] = prefix[start : start + 22]
            else:
                start = prefix.find("BiologicalBeing_")
                self.filters["being"] = prefix[start : start + 26]

    def _parse_dict(self, d: dict, prefix: str) -> None:
        """Parse a dictionary

        Attributes
        ----------
        d: dict
            The dictionary to parse
        prefix: str
            The prefix key
        """

        if not d:
            self._parse_primitive(d, prefix)

        for k, v in d.items():
            self.parser.get(type(v), self.parser["any"])(v, f"{prefix}.{k}")

    def _parse_list(self, l: list, prefix: str) -> None:
        """Parse a list"""

        if not l:
            self._parse_primitive(l, prefix)

        for item in l:
            suffix = item.alias if hasattr(item, "alias") else type(item).__name__
            self.parser.get(type(item), self.parser["any"])(item, f"{prefix}.{suffix}")

    def parse_dataclass(self, data: dataclass, prefix: str = None) -> None:
        """Parse the field of a dataclass

        Attributes
        ----------
        data: dataclass
            The dataclass to parse
        prefix: str
            The prefix key
        """

        if prefix is None:
            prefix = data.alias

        for field in fields(data):
            attribute = getattr(data, field.name)

            self.parser.get(type(attribute), self.parser["any"])(
                attribute, f"{prefix}.{field.name}"
            )

    def _filter(self) -> dict:
        """Filter the metadata

        Returns
        -------
        base: dict
            A flatten dictionary of the filtered metadata
        """

        if self.filters["image"] is None:
            return self.parsed

        dataset = {k: v for k, v in self.parsed.items() if k.startswith("Dataset")}
        base = {k: v for k, v in self.parsed.items() if k.startswith("Study")}
        beings = {
            k: v for k, v in self.parsed.items() if k.startswith("BiologicalBeing")
        }

        # Filter the Dataset with the Observation linked to the slide
        base.update({k: v for k, v in dataset.items() if self.filters["image"] in k})
        base.update({k: v for k, v in dataset.items() if self.filters["slide"] in k})

        observation = {k: v for k, v in dataset.items() if self.filters["obs"] in k}
        base.update({k: v for k, v in observation.items() if "slides" not in k})

        # Filter the Biological Being
        being = {k: v for k, v in beings.items() if self.filters["being"] in k}
        base.update({k: v for k, v in being.items() if "slides" not in k})
        base.update({k: v for k, v in being.items() if self.filters["slide"] in k})

        return base

    def _remove_empty_variables(self) -> None:
        """Remove empty variables from the parsed metadata"""

        self.parsed = {k: v for k, v in self.parsed.items() if v}

    def parse(self, filters: dict = None) -> None:
        """Parse the BP metadata

        Attributes
        ----------
        filters: dict
            Filters to return a subset of the metadata

        Returns
        -------
        parsed: dict
            A flatten dictionary of the parsed and filtered metadata
        """

        if filters:
            self.filters.update(filters)

        for dataset in self.datasets:
            self.parser.get("any")(dataset, dataset.alias)

        for study in self.studies:
            self.parser.get("any")(study, study.alias)

        for being in self.beings:
            self.parser.get("any")(being, being.alias)

        self._remove_empty_variables()

        return self._filter()
