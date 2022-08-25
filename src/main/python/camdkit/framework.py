import typing
import numbers
from fractions import Fraction
from enum import Enum
import dataclasses

INT_MAX = 2147483647 # 2^31 - 1

class Sampling(Enum):
  STATIC = "Static"
  REGULAR = "Regular"

@dataclasses.dataclass
class Dimensions:
  "Height and width of a rectangular area"
  height: numbers.Real
  width: numbers.Real


class Parameter:
  """Metadata parameter base class"""

  @staticmethod
  def validate(value) -> bool:
    raise NotImplementedError

  @staticmethod
  def to_json(value: typing.Any) -> typing.Any:
    raise NotImplementedError

  @staticmethod
  def from_json(value: typing.Any) -> typing.Any:
    raise NotImplementedError

class IntegerDimensionsParameter(Parameter):

  @staticmethod
  def validate(value) -> bool:
    """The height and width shall be each be an integer in the range (0..2,147,483,647]."""

    if not isinstance(value, Dimensions):
      return False

    if not isinstance(value.height, numbers.Integral) or not isinstance(value.width, numbers.Integral):
      return False

    if value.height <= 0 or value.width <= 0 or value.height > INT_MAX or value.width > INT_MAX:
      return False

    return True

  @staticmethod
  def to_json(value: typing.Any) -> typing.Any:
    return dataclasses.asdict(value)

  @staticmethod
  def from_json(value: typing.Any) -> typing.Any:
    return Dimensions(**value)

class StringParameter(Parameter):

  @staticmethod
  def validate(value) -> bool:
    """The parameter shall be a Unicode string betwee 0 and 1023 codepoints."""
    return isinstance(value, str) and len(value) < 1024

  @staticmethod
  def to_json(value: typing.Any) -> typing.Any:
    return str(value)

  @staticmethod
  def from_json(value: typing.Any) -> typing.Any:
    return str(value)

class StrictlyPostiveRationalParameter(Parameter):

  @staticmethod
  def validate(value) -> bool:
    """The parameter shall be a rational number whose numerator and denominator are in the range (0..2,147,483,647]."""

    if not isinstance(value, numbers.Rational):
      return False

    if value.numerator < 0 or value.denominator < 0 or value.numerator > INT_MAX or value.denominator > INT_MAX:
      return False

    return True

  @staticmethod
  def to_json(value: typing.Any) -> typing.Any:
    return str(value)

  @staticmethod
  def from_json(value: typing.Any) -> typing.Any:
    return Fraction(value)

class StrictlyPositiveIntegerParameter(Parameter):

  @staticmethod
  def validate(value) -> bool:
    """The parameter shall be a integer in the range (0..2,147,483,647]."""

    return isinstance(value, numbers.Integral) and value > 0

  @staticmethod
  def to_json(value: typing.Any) -> typing.Any:
    return value

  @staticmethod
  def from_json(value: typing.Any) -> typing.Any:
    return int(value)

class ParameterContainer:
  def __init__(self) -> None:
    self._values = {k: None for k in self._params}

  @classmethod
  def __init_subclass__(cls) -> None:
    cls._params = {}
    for f in dir(cls):
      desc = getattr(cls, f)

      if not isinstance(desc, Parameter):
        continue

      if not hasattr(desc, "canonical_name") or not isinstance(desc.canonical_name, str):
        raise TypeError("A Parameter must have a canonical_name parameter")

      if not hasattr(desc, "sampling") or not isinstance(desc.sampling, Sampling):
        raise TypeError("A Parameter must have a sampling parameter")

      cls._params[f] = desc

      def _gen_getter(f):
        def getter(self):
          return self._values[f]
        return getter
      def _gen_setter(f):
        def setter(self, value):
          if value is not None:
            if self._params[f].sampling is Sampling.STATIC:
              if not self._params[f].validate(value):
                raise ValueError
            elif self._params[f].sampling is Sampling.REGULAR:
              if not (isinstance(value, tuple) and all(self._params[f].validate(s) for s in value)):
                raise ValueError
            else:
              raise ValueError
          self._values[f] = value
        return setter

      setattr(cls, f, property(_gen_getter(f), _gen_setter(f)))

    def _auto__call__init__(self, *a, **kwargs):
      for base in cls.__bases__:
        base.__init__(self, *a, **kwargs)
      ParameterContainer.__init__(self)
      cls._saved_init(self, *a, **kwargs)
    cls._saved_init = cls.__init__
    cls.__init__ = _auto__call__init__

  def to_json(self) -> dict:
    obj = {}
    for k, desc in self._params.items():
      value = self._values[k]
      if value is None:
        obj[desc.canonical_name] = None
      if desc.sampling is Sampling.STATIC:
        obj[desc.canonical_name] = desc.to_json(self._values[k])
      elif desc.sampling is Sampling.REGULAR:
        obj[desc.canonical_name] = tuple(map(desc.to_json, value))
      else:
        raise ValueError

    return obj

  def from_json(self, json_dict: dict):
    for k, v in json_dict.items():
      if k in self._params:
        desc = self._params[k]
        if desc.sampling is Sampling.STATIC:
          self._values[k] = desc.from_json(v)
        elif desc.sampling is Sampling.REGULAR:
          self._values[k] = tuple(map(desc.from_json, v))
        else:
          raise ValueError

  @classmethod
  def get_documentation(cls) -> dict:
    doc = {}
    for _, desc in cls._params.items():
      doc[desc.canonical_name] = {
        "description" : desc.__doc__,
        "constraints" : desc.validate.__doc__,
        "sampling" : str(desc.sampling.value)
      }
    return doc