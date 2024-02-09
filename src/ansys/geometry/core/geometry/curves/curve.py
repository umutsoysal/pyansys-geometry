# Copyright (C) 2023 - 2024 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
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
"""Provides the ``Curve`` class."""
from abc import ABC, abstractmethod

from ansys.geometry.core.geometry.curves.curve_evaluation import CurveEvaluation
from ansys.geometry.core.geometry.parameterization import Parameterization
from ansys.geometry.core.math import Matrix44, Point3D
from ansys.geometry.core.typing import Real


class Curve(ABC):
    """
    Curve abstract base class.

    Represents a 3D curve.
    """

    @abstractmethod
    def parameterization(self) -> Parameterization:
        """Parameterization of the curve."""
        return

    @abstractmethod
    def contains_param(self, param: Real) -> bool:
        """Test whether a parameter is within the parametric range of the curve."""
        return

    @abstractmethod
    def contains_point(self, point: Point3D) -> bool:
        """
        Test whether the point is contained by the curve.

        The point can either lie within it, or on its boundary.
        """
        return

    @abstractmethod
    def transformed_copy(self, matrix: Matrix44) -> "Curve":
        """Create a transformed copy of the curve."""
        return

    @abstractmethod
    def __eq__(self, other: "Curve") -> bool:
        """Determine if two curves are equal."""
        return

    @abstractmethod
    def evaluate(self, parameter: Real) -> CurveEvaluation:
        """Evaluate the curve at the given parameter."""
        return

    @abstractmethod
    def project_point(self, point: Point3D) -> CurveEvaluation:
        """
        Project a point to the curve.

        This returns the evaluation at the closest point.
        """
        return

    # TODO: Implement more curve methods
    # as_spline
    # get_length
    # get_polyline
    # intersect_curve
    # is_coincident
