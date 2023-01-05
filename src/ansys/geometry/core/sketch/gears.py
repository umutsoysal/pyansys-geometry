"""Module for sketching gears."""

from beartype import beartype as check_input_types
from beartype.typing import List, Tuple
import numpy as np
from pint import Quantity
import pyvista as pv

from ansys.geometry.core.math import Point2D
from ansys.geometry.core.misc import UNIT_ANGLE, UNITS, Distance, check_pint_unit_compatibility
from ansys.geometry.core.sketch.arc import Arc
from ansys.geometry.core.sketch.face import SketchFace
from ansys.geometry.core.sketch.segment import Segment
from ansys.geometry.core.typing import Real


class Gear(SketchFace):
    """Base class for sketching gears."""

    def __init__(self):
        """Constructor method for gears."""
        super().__init__()

    @property
    def visualization_polydata(self) -> pv.PolyData:
        """
        VTK polydata representation for PyVista visualization.

        The representation lies in the X/Y plane within
        the standard global Cartesian coordinate system.

        Returns
        -------
        pyvista.PolyData
            VTK pyvista.Polydata configuration.
        """
        return pv.merge([edge.visualization_polydata for edge in self._edges])


class DummyGear(Gear):
    """Dummy gear sketching class.

    Parameters
    ----------
    origin : Point2D
        Origin of the gear.
    outer_radius : Distance
        Outer radius of the gear.
    inner_radius : Distance
        Inner radius of the gear.
    n_teeth : int
        Number of teeth of the gear.
    """

    @check_input_types
    def __init__(
        self, origin: Point2D, outer_radius: Distance, inner_radius: Distance, n_teeth: int
    ):
        """Constructor method for a dummy gear."""
        # Call the parent ctor
        super().__init__()

        # Let's compute auxiliary variables
        repeat_angle = 2 * np.pi / n_teeth
        tooth_angle = 0.475 * repeat_angle
        gap_angle = repeat_angle - tooth_angle

        # Now, let's loop over all teeth to build the sketch
        for tooth_idx in range(n_teeth):
            # Three angles need to be computed: starting tooth angle,
            # ending tooth angle (==starting gap angle) and ending gap angle
            start_ang = tooth_idx * repeat_angle
            inter_ang = start_ang + tooth_angle
            end_ang = inter_ang + gap_angle

            # Let's compute the sin and cos values for these angles
            sin_inter = np.sin(inter_ang)
            cos_inter = np.cos(inter_ang)
            sin_end = np.sin(end_ang)
            cos_end = np.cos(end_ang)

            # Let's define the points for drawing the arcs and segments involved
            outer_arc_start = Point2D(
                [
                    outer_radius.value.m * np.cos(start_ang),
                    outer_radius.value.m * np.sin(start_ang),
                ],
                unit=outer_radius.unit,
            )
            outer_arc_end = Point2D(
                [outer_radius.value.m * cos_inter, outer_radius.value.m * sin_inter],
                unit=outer_radius.unit,
            )
            inner_arc_start = Point2D(
                [inner_radius.value.m * cos_inter, inner_radius.value.m * sin_inter],
                unit=inner_radius.unit,
            )
            inner_arc_end = Point2D(
                [inner_radius.value.m * cos_end, inner_radius.value.m * sin_end],
                unit=inner_radius.unit,
            )
            next_outer_arc_start = Point2D(
                [outer_radius.value.m * cos_end, outer_radius.value.m * sin_end],
                unit=outer_radius.unit,
            )

            # Now, let's proceed to draw the arcs and segments
            self._edges.append(
                Arc(center=origin, start=outer_arc_start + origin, end=outer_arc_end + origin)
            )
            self._edges.append(Segment(start=outer_arc_end + origin, end=inner_arc_start + origin))
            self._edges.append(
                Arc(center=origin, start=inner_arc_start + origin, end=inner_arc_end + origin)
            )
            self._edges.append(
                Segment(start=inner_arc_end + origin, end=next_outer_arc_start + origin)
            )


class SpurGear(Gear):
    """Class for sketching spur gears.

    Parameters
    ----------
    origin : Point2D
        Origin of the spur gear.
    module : Real
        Module of the spur gear. This is also the ratio between the pitch circle
        diameter in millimeters and the number of teeth.
    pressure_angle : Quantity
        Pressure angle of the spur gear.
    n_teeth : int
        Number of teeth of the spur gear.
    """

    @check_input_types
    def __init__(self, origin: Point2D, module: Real, pressure_angle: Quantity, n_teeth: int):
        """Constructor for spur gears."""
        # Call the parent ctor
        super().__init__()

        # Additional checks for inputs
        check_pint_unit_compatibility(pressure_angle.u, UNIT_ANGLE)

        # Store input parameters
        self._origin = origin
        self._module = module
        self._pressure_angle = pressure_angle.to(UNIT_ANGLE)
        self._n_teeth = n_teeth

        # Compute additional needed values
        self._ref_diameter = self.module * self.n_teeth
        self._base_diameter = self.ref_diameter * np.cos(self.pressure_angle.m)
        self._addendum = self.module
        self._dedendum = 1.25 * self.module
        self._tip_diameter = self.ref_diameter + 2 * self.module
        self._root_diameter = self.ref_diameter - 2.5 * self.module

        # TODO: To be properly implemented (sketching)...
        self._sketch_spur_gear()

    @property
    def origin(self) -> Point2D:
        """Origin of the spur gear."""
        return self._origin

    @property
    def module(self) -> Real:
        """Module of the spur gear."""
        return self._module

    @property
    def pressure_angle(self) -> Quantity:
        """Pressure angle of the spur gear."""
        return self._pressure_angle

    @property
    def n_teeth(self) -> int:
        """Number of teeth of the spur gear."""
        return self._n_teeth

    @property
    def ref_diameter(self) -> Real:
        """Reference diameter of the spur gear."""
        return self._ref_diameter

    @property
    def base_diameter(self) -> Real:
        """Base diameter of the spur gear."""
        return self._base_diameter

    @property
    def addendum(self) -> Real:
        """Addendum of the spur gear."""
        return self._addendum

    @property
    def dedendum(self) -> Real:
        """Dedendum of the spur gear."""
        return self._dedendum

    @property
    def tip_diameter(self) -> Real:
        """Tip diameter of the spur gear."""
        return self._tip_diameter

    @property
    def root_diameter(self) -> Real:
        """Root diameter of the spur gear."""
        return self._root_diameter

    def _sketch_spur_gear(self) -> None:
        """Private method in charge of generating the arcs and segments
        needed to sketch the Spur Gear from its properties previously defined.
        """

        # Let's sketch a single tooth first
        tooth_lines = self._sketch_single_tooth_spur_gear()

        # Now, for all teeth, let's rotate those values
        rotate_angle = 2 * np.pi / self.n_teeth
        last_point = None
        for tooth_idx in range(self.n_teeth):
            # Rotate the tooth points by a given angle
            x_i, y_i = self._rotate_curve(tooth_idx * rotate_angle, tooth_lines[0], tooth_lines[2])
            x_m, y_m = self._rotate_curve(tooth_idx * rotate_angle, tooth_lines[1], tooth_lines[3])

            if last_point:
                # Add the closing arc from the previous tooth
                self._edges.extend(
                    self._generate_arcs(
                        [last_point[0], x_i[0]], [last_point[1], y_i[0]], closing_involute=True
                    )
                )

            # Generate the arcs from involute curve
            self._edges.extend(self._generate_arcs(x_i, y_i))
            # Add the closing involute-to-mirror arc
            self._edges.extend(
                self._generate_arcs([x_i[-1], x_m[0]], [y_i[-1], y_m[0]], closing_involute=True)
            )
            # Generate the arcs from mirrored involute curve
            self._edges.extend(self._generate_arcs(x_m, y_m))
            # Update the last point value
            last_point = (x_m[-1], y_m[-1])

        # When coming out of the loop, we need to close with the starting tooth
        self._edges.extend(
            self._generate_arcs(
                [last_point[0], tooth_lines[0][0]],
                [last_point[1], tooth_lines[2][0]],
                closing_involute=True,
            )
        )

    def _sketch_single_tooth_spur_gear(
        self,
    ) -> Tuple[List[Real], List[Real], List[Real], List[Real]]:
        """Private method to sketch a single tooth.

        Returns
        -------
        Tuple[List[Real], List[Real], List[Real], List[Real]]
            X and Y values for the tooth grouped together as follows: (x_i, x_m, y_i, y_m)
        """
        # Compute the involute with the smallest of both
        #
        # FYI: Max angle is slightly less than  90deg
        diam = self.root_diameter if self.root_diameter < self.base_diameter else self.base_diameter
        x_i, y_i, t_i = self._involute(diam / 2, self.tip_diameter / 2, np.pi / 2.1)

        # Align the involute curve to cross the pitch diameter
        x_i, y_i = self._align_involute(x_i, y_i, t_i)

        # Get the mirrored section of the involute
        x_m = list(reversed(x_i))
        y_m = [-y for y in list(reversed(y_i))]

        # Rotate the mirrored curve by the circular tooth angle
        # First, compute the tooth thickness = circular pitch (== module * pi) / (2 + backlash)
        # Then, the angle will be = thickness * 2 / diametral pitch
        circular_tooth_thickness = (self.module * np.pi) / 2.05
        circular_tooth_angle = circular_tooth_thickness * 2 / (self.module * self.n_teeth)
        x_m, y_m = self._rotate_curve(circular_tooth_angle, x_m, y_m)

        # Now that we have the whole tooth points, return them
        return (x_i, x_m, y_i, y_m)

    def _involute(
        self, radius: Real, max_radius: Real, max_theta: Real, steps: int = 30
    ) -> Tuple[List[Real], List[Real]]:
        """Generates the involute points discretization of a curve.

        Parameters
        ----------
        radius : Real
            The departing radius for computing the involute.
        max_radius : Real
            The maximum radius up to which the involute will be computed.
        max_theta : Real
            The maximum angle up to which the involute will be computed.
        steps : int, optional
            The number of steps used to discretize the curve, by default 30.

        Returns
        -------
        Tuple[List[Real], List[Real], List[Real]]
            A three-element tuple containing a list of X, Y and theta values
            defining the involute.
        """
        # Instantiate the containers which will store the results
        x_p = []
        y_p = []
        t_p = []

        # Define the delta angle to be increased in each step
        dtheta = max_theta / steps

        # Iterate over the defined steps
        for i in range(steps):
            # Compute the involute X, Y and curve angle values
            c_dtheta = np.cos(i * dtheta)
            s_dtheta = np.sin(i * dtheta)
            invol_x = radius * (c_dtheta + i * dtheta * s_dtheta)
            invol_y = radius * (s_dtheta - i * dtheta * c_dtheta)
            invol_ang = np.arctan2(invol_y, invol_x)
            dist = np.sqrt(invol_x**2 + invol_y**2)

            # Appending values to result containers
            x_p.append(invol_x)
            y_p.append(invol_y)
            t_p.append(invol_ang)

            # Check if we overcame the max_radius...
            if dist > max_radius:
                # We passed the limit... let's readjust (linear interp to the max)
                adjustment = (max_radius - radius) / (dist - radius)
                x_p[-1] = x_p[-2] * (1 - adjustment) + invol_x * adjustment
                y_p[-1] = y_p[-2] * (1 - adjustment) + invol_y * adjustment
                t_p[-1] = t_p[-2] * (1 - adjustment) + invol_ang * adjustment
                break

        return (x_p, y_p, t_p)

    def _align_involute(
        self, x_p: List[Real], y_p: List[Real], t_p: List[Real]
    ) -> Tuple[List[Real], List[Real]]:
        """Private method in charge of aligning the discretized values
        of the involute curve.

        Parameters
        ----------
        x_p : List[Real]
            X-elements defining the involute curve to align.
        y_p : List[Real]
            Y-elements defining the involute curve to align.
        t_p : List[Real]
            Angles defining the involute curve to align.

        Returns
        -------
        Tuple[List[Real], List[Real]]
            The set of X and Y elements aligned.

        Raises
        ------
        ValueError
            In case no alignment angle is found.
        """

        # Compute the angle where the involute curve crosses the circle
        theta_cross = None
        pitch_circle_radius = (self.module * self.n_teeth) / 2
        rr = pitch_circle_radius * pitch_circle_radius
        for idx in range(0, len(x_p) - 1):
            rr_2 = x_p[idx + 1] * x_p[idx + 1] + y_p[idx + 1] * y_p[idx + 1]
            if rr_2 > rr:
                # This means we passed the angle, adjust!
                r1 = np.sqrt(x_p[idx] * x_p[idx] + y_p[idx] * y_p[idx])
                r2 = np.sqrt(rr_2)
                adjustment = (pitch_circle_radius - r1) / (r2 - r1)
                theta_cross = t_p[idx] * (1 - adjustment) + t_p[idx + 1] * adjustment
                break

        # If no angle is found... fail!
        if not theta_cross:  # pragma: no cover
            raise ValueError("Error in involute alignment! Check values and implementation")

        # Proceed to alignment using -theta_cross
        return self._rotate_curve(-theta_cross, x_p, y_p)

    def _rotate_curve(
        self, angle: Real, x_p: List[Real], y_p: List[Real]
    ) -> Tuple[List[Real], List[Real]]:
        """Private method used for rotating X,Y elements defining a curve
        by a given angle.

        Parameters
        ----------
        angle : Real
            Angle (in radians) to rotate the X,Y elements.
        x_p : List[Real]
            X-elements of the curve to rotate.
        y_p : List[Real]
            Y-elements of the curve to rotate.

        Returns
        -------
        Tuple[List[Real], List[Real]]
            The X and Y elements of the rotated curve.
        """

        # Compute the sin and cos values of the angle
        c_ang = np.cos(angle)
        s_ang = np.sin(angle)

        # Rotate the points
        x_r = []
        y_r = []
        for x, y in zip(x_p, y_p):
            x_r.append(c_ang * x - s_ang * y)
            y_r.append(s_ang * x + c_ang * y)

        return (x_r, y_r)

    def _generate_arcs(
        self, x_p: List[Real], y_p: List[Real], closing_involute: bool = False
    ) -> List[Arc]:
        """Private method used for generating the arcs of involute curves
        when sketching spur gears.

        Parameters
        ----------
        x_p : List[Real]
            X-elements defining the involute curve.
        y_p : List[Real]
            Y-elements defining the involute curve.
        closing_involute : bool, optional
            Shortcut for joining involute curves, by default False.

        Returns
        -------
        List[Arc]
            The list of arcs defining the requested curve.
        """

        # Initialize results container
        arcs = []

        # Generate Point2D objects from given X, Y values (remember, they are in mm)
        points = [
            Point2D(
                [x_i + self.origin.x.to(UNITS.mm).m, y_i + self.origin.y.to(UNITS.mm).m],
                unit=UNITS.mm,
            )
            for (x_i, y_i) in zip(x_p, y_p)
        ]

        if not closing_involute:

            # Initiate preliminary arc object - lives outside the scope of the loop
            preliminary_arc = None

            for idx in range(len(points) - 2):
                # Compute a preliminary arc taking into account three points
                preliminary_arc = Arc.from_three_points(
                    start=points[idx], inter=points[idx + 1], end=points[idx + 2]
                )

                # Keep only the first two points as part of the arc... use the
                # needed values from the preliminary arc
                arcs.append(
                    Arc(
                        center=preliminary_arc.center,
                        start=points[idx],
                        end=points[idx + 1],
                        clockwise=preliminary_arc.is_clockwise,
                    )
                )

            # Once the loop has finished... extend the last arc
            arcs.append(
                Arc(
                    center=preliminary_arc.center,
                    start=points[-2],
                    end=points[-1],
                    clockwise=preliminary_arc.is_clockwise,
                )
            )

        else:
            # We should only enter this branch if we are closing the involute curves...
            # ... which means that we only have two points in our list...
            #
            # Just in case, let us only take the first and last elements of the given list
            arcs.append(
                Arc(
                    center=self.origin,
                    start=points[0],
                    end=points[-1],
                )
            )

        # Finally, return the requested arcs
        return arcs