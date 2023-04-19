""" Provides the ``Circle`` class."""
from functools import cached_property

from beartype import beartype as check_input_types
from beartype.typing import Union
import numpy as np
from pint import Quantity

from ansys.geometry.core.math import (
    UNITVECTOR3D_X,
    UNITVECTOR3D_Z,
    Matrix44,
    Point3D,
    UnitVector3D,
    Vector3D,
)
from ansys.geometry.core.misc import Accuracy, Distance
from ansys.geometry.core.primitives.curve_evaluation import CurveEvaluation
from ansys.geometry.core.primitives.parameterization import (
    Interval,
    Parameterization,
    ParamForm,
    ParamType,
)
from ansys.geometry.core.typing import Real, RealSequence


class Circle:
    """
    Provides 3D ``Circle`` representation.

    Parameters
    ----------
    origin : Union[~numpy.ndarray, RealSequence, Point3D]
        Origin of the circle.
    radius : Union[Quantity, Distance, Real]
        Radius of the circle.
    reference : Union[~numpy.ndarray, RealSequence, UnitVector3D, Vector3D]
        X-axis direction.
    axis : Union[~numpy.ndarray, RealSequence, UnitVector3D, Vector3D]
        Z-axis direction.
    """

    @check_input_types
    def __init__(
        self,
        origin: Union[np.ndarray, RealSequence, Point3D],
        radius: Union[Quantity, Distance, Real],
        reference: Union[np.ndarray, RealSequence, UnitVector3D, Vector3D] = UNITVECTOR3D_X,
        axis: Union[np.ndarray, RealSequence, UnitVector3D, Vector3D] = UNITVECTOR3D_Z,
    ):
        self._origin = Point3D(origin) if not isinstance(origin, Point3D) else origin

        self._reference = (
            UnitVector3D(reference) if not isinstance(reference, UnitVector3D) else reference
        )
        self._axis = UnitVector3D(axis) if not isinstance(axis, UnitVector3D) else axis

        if not self._reference.is_perpendicular_to(self._axis):
            raise ValueError("Circle reference (dir_x) and axis (dir_z) must be perpendicular.")

        self._radius = radius if isinstance(radius, Distance) else Distance(radius)
        if self._radius.value <= 0:
            raise ValueError("Radius must be a real positive value.")

    @property
    def origin(self) -> Point3D:
        """Origin of the circle."""
        return self._origin

    @property
    def radius(self) -> Quantity:
        """Radius of the circle."""
        return self._radius.value

    @property
    def diameter(self) -> Quantity:
        """Diameter of the circle."""
        return 2 * self.radius

    @property
    def perimeter(self) -> Quantity:
        """Perimeter of the circle."""
        return 2 * np.pi * self.radius

    @property
    def area(self) -> Quantity:
        """Area of the circle."""
        return np.pi * self.radius**2

    @property
    def dir_x(self) -> UnitVector3D:
        """X-direction of the circle."""
        return self._reference

    @property
    def dir_y(self) -> UnitVector3D:
        """Y-direction of the circle."""
        return self.dir_z.cross(self.dir_x)

    @property
    def dir_z(self) -> UnitVector3D:
        """Z-direction of the circle."""
        return self._axis

    @check_input_types
    def __eq__(self, other: "Circle") -> bool:
        """Equals operator for the ``Circle`` class."""
        return (
            self._origin == other._origin
            and self._radius == other._radius
            and self._reference == other._reference
            and self._axis == other._axis
        )

    def evaluate(self, parameter: Real) -> "CircleEvaluation":
        """
        Evaluate the circle at the given parameter.

        Parameters
        ----------
        parameter : Real
            The parameter at which to evaluate the circle.

        Returns
        -------
        CircleEvaluation
            The resulting evaluation.
        """
        return CircleEvaluation(self, parameter)

    def transformed_copy(self, matrix: Matrix44) -> "Circle":
        """
        Creates a transformed copy of the circle based on a given transformation matrix.

        Parameters
        ----------
        matrix : Matrix44
            The transformation matrix to apply to the circle.

        Returns
        -------
        Circle
            A new circle that is the transformed copy of the original circle.
        """
        new_point = self.origin.transform(matrix)
        new_reference = self._reference.transform(matrix)
        new_axis = self._axis.transform(matrix)
        return Circle(
            new_point,
            self.radius,
            UnitVector3D(new_reference[0:3]),
            UnitVector3D(new_axis[0:3]),
        )

    def mirrored_copy(self) -> "Circle":
        """
        Creates a mirrored copy of the circle along the y-axis.

        Returns
        -------
        Circle
            A new circle that is a mirrored copy of the original circle.
        """

        return Circle(self.origin, self.radius, -self._reference, -self._axis)

    def project_point(self, point: Point3D) -> "CircleEvaluation":
        """
        Project a point onto the circle and return its ``CircleEvaluation``.

        Parameters
        ----------
        point : Point3D
            The point to project onto the circle.

        Returns
        -------
        CircleEvaluation
            The resulting evaluation.
        """
        origin_to_point = point - self.origin
        dir_in_plane = UnitVector3D.from_points(
            Point3D([0, 0, 0]), origin_to_point - ((origin_to_point * self.dir_z) * self.dir_z)
        )
        if dir_in_plane.is_zero:
            return CircleEvaluation(self, 0)

        t = np.arctan2(self.dir_y.dot(dir_in_plane), self.dir_x.dot(dir_in_plane))
        return CircleEvaluation(self, t)

    def is_coincident_circle(self, other: "Circle") -> bool:
        """
        Determine if this circle is coincident with another.

        Parameters
        ----------
        other : Circle
            The circle to determine coincidence with.

        Returns
        -------
        bool
            Returns true if this circle is coincident with the other.
        """
        return (
            Accuracy.length_is_equal(self.radius.m, other.radius.m)
            and self.origin == other.origin
            and self.dir_z == other.dir_z
        )

    def get_parameterization(self) -> Parameterization:
        """
        The parameter of a circle specifies the clockwise angle around the axis
        (right hand corkscrew law), with a zero parameter at `dir_x` and a period
        of 2*pi.

        Returns
        -------
        Parameterization
            Information about how a circle is parameterized.
        """
        return Parameterization(ParamForm.PERIODIC, ParamType.CIRCULAR, Interval(0, 2 * np.pi))


class CircleEvaluation(CurveEvaluation):
    """
    Provides ``Circle`` evaluation at a certain parameter.

    Parameters
    ----------
    circle: ~ansys.geometry.core.primitives.circle.Circle
        The ``Circle`` object to be evaluated.
    parameter: Real
        The parameter at which the ``Circle`` evaluation is requested.
    """

    def __init__(self, circle: Circle, parameter: Real) -> None:
        """``CircleEvaluation`` class constructor."""
        self._circle = circle
        self._parameter = parameter

    @property
    def circle(self) -> Circle:
        """The circle being evaluated."""
        return self._circle

    @property
    def parameter(self) -> Real:
        """The parameter that the evaluation is based upon."""
        return self._parameter

    @cached_property
    def position(self) -> Point3D:
        """
        The position of the evaluation.

        Returns
        -------
        Point3D
            The point that lies on the circle at this evaluation.
        """
        return (
            self.circle.origin
            + ((self.circle.radius * np.cos(self.parameter)) * self.circle.dir_x).m
            + ((self.circle.radius * np.sin(self.parameter)) * self.circle.dir_y).m
        )

    @cached_property
    def tangent(self) -> UnitVector3D:
        """
        The tangent of the evaluation.

        Returns
        -------
        UnitVector3D
            The tangent unit vector to the circle at this evaluation.
        """
        return (
            np.cos(self.parameter) * self.circle.dir_y - np.sin(self.parameter) * self.circle.dir_x
        )

    @cached_property
    def normal(self) -> UnitVector3D:
        """
        The normal to the circle.

        Returns
        -------
        UnitVector3D
            The normal unit vector to the circle at this evaluation.
        """
        return UnitVector3D(
            np.cos(self.parameter) * self.circle.dir_x + np.sin(self.parameter) * self.circle.dir_y
        )

    @cached_property
    def first_derivative(self) -> Vector3D:
        """
        The first derivative of the evaluation. The first derivative is in the direction of the
        tangent and has a magnitude equal to the velocity (rate of change of position) at that
        point.

        Returns
        -------
        Vector3D
            The first derivative of this evaluation.
        """
        return self.circle.radius.m * (
            np.cos(self.parameter) * self.circle.dir_y - np.sin(self.parameter) * self.circle.dir_x
        )

    @cached_property
    def second_derivative(self) -> Vector3D:
        """
        The second derivative of the evaluation.

        Returns
        -------
        Vector3D
            The second derivative of this evaluation.
        """
        return -self.circle.radius.m * (
            np.cos(self.parameter) * self.circle.dir_x + np.sin(self.parameter) * self.circle.dir_y
        )

    @cached_property
    def curvature(self) -> Real:
        """
        The curvature of the circle.

        Returns
        -------
        Real
            The curvature of the circle.
        """
        return 1 / np.abs(self.circle.radius.m)
