# Copyright 2018 - 2019 Fabian Wenzelmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math

class Fraction(object):
    def __init__(self, numerator=0, denominator=1):
        if denominator == 0:
            raise ZeroDivisionError()
        self.numerator = numerator
        self.denominator = denominator

    def __get_tuple(self):
        return self.numerator, self.denominator

    @staticmethod
    def __unpack_both(first, second):
        a, b = first.__get_tuple()
        c, d = second.__get_tuple()
        return a, b, c, d

    def __add__(self, other):
        a, b, c, d = Fraction.__unpack_both(self, other)
        return Fraction(a * d + c * b, b * d)

    def __sub__(self, other):
        a, b, c, d = Fraction.__unpack_both(self, other)
        return Fraction(a * d - c * b, b * d)

    def __mul__(self, other):
        a, b, c, d = Fraction.__unpack_both(self, other)
        return Fraction(a * c, b * d)

    def __div__(self, other):
        a, b, c, d = Fraction.__unpack_both(self, other)
        return Fraction(a * d, b * c)

    def normalize(self):
        a, b, = self.__get_tuple()
        gcd = math.gcd(a, b)
        return Fraction(a // gcd, b // gcd)

    def __str__(self):
        return '%d / %d' % (self.numerator, self.denominator)

    def __repr__(self):
        return str(self)

    def split(self):
        a, b = self.__get_tuple()
        div = a // b
        rest = self - Fraction(div)
        return div, rest

    def is_zero(self):
        return self.numerator == 0
