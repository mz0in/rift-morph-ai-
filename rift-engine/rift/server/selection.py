from dataclasses import dataclass
import itertools
from typing import Iterable, Union

from rift.lsp.types import Range, Position, TextDocumentContentChangeEvent
from rift.util.ofdict import todict, ofdict


class RangeSet:
    ranges: set[Range]

    def __init__(self, ranges: "Iterable[Union[Range, RangeSet]]" = []):
        self.ranges = set()
        for range in ranges:
            if isinstance(range, RangeSet):
                self.ranges.update(range.ranges)
            elif isinstance(range, Range):
                self.add(range)
            else:
                raise TypeError(f"Expected Range or RangeSet, got {type(range)}")

    def __todict__(self):
        return list(self.ranges)

    @classmethod
    def __ofdict__(cls, d):
        ranges = ofdict(list[Range], d)
        return cls(ranges)

    @property
    def is_empty(self):
        return all(len(r) == 0 for r in self.ranges)

    def add(self, range: Range):
        acc = range
        ranges = set()
        for r in self.ranges:
            if acc.end in r or acc.start in r:
                acc = Range.union([acc, r])
            else:
                ranges.add(r)
        ranges.add(acc)
        self.ranges = ranges

    def normalize(self):
        classes: list[Range] = []
        for r in self.ranges:
            if len(r) == 0:
                continue
            ins = []
            outs = []
            for c in classes:
                if c.end in r or c.start in r:
                    ins.append(c)
                else:
                    outs.append(c)
            if len(ins) > 0:
                x = Range.union([r] + ins)
                outs.append(x)
            else:
                outs.append(r)
            classes = outs
        return RangeSet(classes)

    def __contains__(self, pos: Position):
        for range in self.ranges:
            if pos in range:
                return True
        return False

    def cover(self):
        if len(self.ranges) == 0:
            raise ValueError("empty range set")
        return Range.union(self.ranges)

    def apply_edit(self, edit: TextDocumentContentChangeEvent):
        if edit.range is None:
            return self
        ranges = set()
        n = len(edit.text)
        δ = n - len(edit.range)
        for range in self.ranges:
            if edit.range.end <= range.start:
                ranges.add(range + δ)
            elif edit.range.start >= range.end:
                ranges.add(range)
            else:
                if edit.range.start in range:
                    ranges.add(Range(range.start, edit.range.start))
                if edit.range.end in range:
                    ranges.add(Range(edit.range.start + n, range.end + δ))
        return RangeSet(ranges)
