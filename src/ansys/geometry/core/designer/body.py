"""Provides the ``Body`` class module."""
from abc import ABC, abstractmethod
from enum import Enum
from functools import wraps

from ansys.api.geometry.v0.bodies_pb2 import (
    CopyRequest,
    SetAssignedMaterialRequest,
    TranslateRequest,
)
from ansys.api.geometry.v0.bodies_pb2_grpc import BodiesStub
from ansys.api.geometry.v0.commands_pb2 import (
    AssignMidSurfaceOffsetTypeRequest,
    AssignMidSurfaceThicknessRequest,
    ImprintCurvesRequest,
    ProjectCurvesRequest,
)
from ansys.api.geometry.v0.commands_pb2_grpc import CommandsStub
from ansys.api.geometry.v0.models_pb2 import EntityIdentifier
from beartype import beartype as check_input_types
from beartype.typing import TYPE_CHECKING, List, Optional, Tuple, Union
from pint import Quantity

from ansys.geometry.core.connection import (
    GrpcClient,
    sketch_shapes_to_grpc_geometries,
    tess_to_pd,
    unit_vector_to_grpc_direction,
)
from ansys.geometry.core.designer.edge import CurveType, Edge
from ansys.geometry.core.designer.face import Face, SurfaceType
from ansys.geometry.core.errors import protect_grpc
from ansys.geometry.core.materials import Material
from ansys.geometry.core.math import IDENTITY_MATRIX44, Matrix44, UnitVector3D
from ansys.geometry.core.misc import DEFAULT_UNITS, Distance, check_type
from ansys.geometry.core.sketch import Sketch
from ansys.geometry.core.typing import Real

if TYPE_CHECKING:  # pragma: no cover
    from pyvista import MultiBlock, PolyData

    from ansys.geometry.core.designer.component import Component
    from ansys.geometry.core.designer.design import MidSurfaceOffsetType


class MidSurfaceOffsetType(Enum):
    """Provides an enum holding the possible types of mid-surface offset by the Geometry service"""

    MIDDLE = 0
    TOP = 1
    BOTTOM = 2
    VARIABLE = 3
    CUSTOM = 4


class IBody(ABC):
    """
    Abstract Body interface. Defines the common methods for a body. TemplateBody and Body both
    inherit from this. All child classes must implement all abstract methods.
    """

    @abstractmethod
    def id(self) -> str:
        """ID of the body."""
        return

    @abstractmethod
    def name(self) -> str:
        """Name of the body."""
        return

    @abstractmethod
    def faces(self) -> List[Face]:
        """All faces within the body.

        Returns
        -------
        List[Face]
        """
        return

    @abstractmethod
    def edges(self) -> List[Edge]:
        """All edges within the body.

        Returns
        -------
        List[Edge]
        """
        return

    @abstractmethod
    def is_alive(self) -> bool:
        """If the body is still alive and has not been deleted."""
        return

    @abstractmethod
    def is_surface(self) -> bool:
        """Check if the body is a planar body."""
        return

    @abstractmethod
    def surface_thickness(self) -> Union[Quantity, None]:
        """Surface thickness of a surface body.

        Notes
        -----
        Only for surface-type bodies which have been assigned a surface thickness.
        """
        return

    @abstractmethod
    def surface_offset(self) -> Union["MidSurfaceOffsetType", None]:
        """Surface offset type of a surface body.

        Notes
        -----
        Only for surface-type bodies which have been assigned a surface offset.
        """
        return

    @abstractmethod
    def volume(self) -> Quantity:
        """Calculated volume of the body.

        Notes
        -----
        When dealing with a planar surface, a value of ``0`` is returned as a volume.
        """
        return

    @abstractmethod
    def assign_material(self, material: Material) -> None:
        """Assigns a material against the design in the active Geometry service instance.

        Parameters
        ----------
        material : Material
            Source material data.
        """
        return

    @abstractmethod
    def add_midsurface_thickness(self, thickness: Quantity) -> None:
        """Adds a mid-surface thickness to a surface body.

        Parameters
        ----------
        thickness : Quantity
            Thickness to be assigned.

        Notes
        -----
        Only surface bodies will be eligible for mid-surface thickness assignment.
        """
        return

    @abstractmethod
    def add_midsurface_offset(self, offset: "MidSurfaceOffsetType") -> None:
        """Adds a mid-surface offset to a surface body.

        Parameters
        ----------
        offset_type : MidSurfaceOffsetType
            Surface offset to be assigned.

        Notes
        -----
        Only surface bodies will be eligible for mid-surface offset assignment.
        """
        return

    @abstractmethod
    def imprint_curves(self, faces: List[Face], sketch: Sketch) -> Tuple[List[Edge], List[Face]]:
        """Imprints all specified geometries onto the specified faces of the body.

        Parameters
        ----------
        faces: List[Face]
            List of faces to imprint the curves of the sketch.
        sketch: Sketch
            All curves to imprint on the faces.

        Returns
        -------
        Tuple[List[Edge], List[Face]]
            All impacted edges and faces from the imprint operation.
        """
        return

    @abstractmethod
    def project_curves(
        self,
        direction: UnitVector3D,
        sketch: Sketch,
        closest_face: bool,
        only_one_curve: Optional[bool] = False,
    ) -> List[Face]:
        """Projects all specified geometries onto the body.

        Parameters
        ----------
        direction: UnitVector3D
            Establishes the direction of the projection.
        sketch: Sketch
            All curves to project on the body.
        closest_face: bool
            Whether to target the closest face with the projection.
        only_one_curve: bool, default: False
            Whether to project only one curve of the entire sketch. When
            ``True``, only one curve is projected.

        Notes
        -----
        The ``only_one_curve`` parameter allows you to optimize the server call because
        projecting curves is an expensive operation. This reduces the workload on the
        server side.

        Returns
        -------
        List[Face]
            All faces from the project curves operation.
        """
        return

    @abstractmethod
    def translate(self, direction: UnitVector3D, distance: Union[Quantity, Distance, Real]) -> None:
        """Translates the geometry body in the specified direction by a given distance.

        Parameters
        ----------
        direction: UnitVector3D
            Direction of the translation.
        distance: Union[Quantity, Distance, Real]
            Magnitude of the translation.

        Returns
        -------
        None
        """
        return

    @abstractmethod
    def copy(self, parent: "Component", name: str = None) -> "Body":
        """Creates a copy of the geometry body and places it under the specified parent.

        Parameters
        ----------
        parent: Component
            The parent component that the new body should live under.
        name: str
            The name to give the new body.

        Returns
        -------
        Body
            Copy of the body.
        """
        return

    @abstractmethod
    def tessellate(self, merge: Optional[bool] = False) -> Union["PolyData", "MultiBlock"]:
        """Tessellate the body and return the geometry as triangles.

        Parameters
        ----------
        merge : bool, default: False
            Whether to merge the body into a single mesh. By default, the
            number of triangles are preserved and only the topology is merged.
            When ``True``, the individual faces of the tessellation are merged.

        Returns
        -------
        ~pyvista.PolyData, ~pyvista.MultiBlock
            Merged :class:`pyvista.PolyData` if ``merge=True`` or a composite dataset.

        Examples
        --------
        Extrude a box centered at the origin to create a rectangular body and
        tessellate it:

        >>> from ansys.geometry.core.misc.units import UNITS as u
        >>> from ansys.geometry.core.sketch import Sketch
        >>> from ansys.geometry.core.math import Plane, Point2D, Point3D, UnitVector3D
        >>> from ansys.geometry.core import Modeler
        >>> modeler = Modeler()
        >>> origin = Point3D([0, 0, 0])
        >>> plane = Plane(origin, direction_x=[1, 0, 0], direction_y=[0, 0, 1])
        >>> sketch = Sketch(plane)
        >>> box = sketch.box(Point2D([2, 0]), 4, 4)
        >>> design = modeler.create_design("my-design")
        >>> my_comp = design.add_component("my-comp")
        >>> body = my_comp.extrude_sketch("my-sketch", sketch, 1 * u.m)
        >>> blocks = body.tessellate()
        >>> blocks
        >>> MultiBlock (0x7f94ec757460)
             N Blocks:	6
             X Bounds:	0.000, 4.000
             Y Bounds:	-1.000, 0.000
             Z Bounds:	-0.500, 4.500

        Merge the body:

        >>> mesh = body.tessellate(merge=True)
        >>> mesh
        PolyData (0x7f94ec75f3a0)
          N Cells:	12
          N Points:	24
          X Bounds:	0.000e+00, 4.000e+00
          Y Bounds:	-1.000e+00, 0.000e+00
          Z Bounds:	-5.000e-01, 4.500e+00
          N Arrays:	0


        """
        return

    @abstractmethod
    def plot(
        self,
        merge: bool = False,
        screenshot: Optional[str] = None,
        use_trame: Optional[bool] = None,
        **plotting_options: Optional[dict],
    ) -> None:
        """Plot the body.

        Parameters
        ----------
        merge : bool, default: False
            Whether to merge the body into a single mesh. By default, the
            number of triangles are preserved and only the topology is merged.
            When ``True``, the individual faces of the tessellation are merged.
        screenshot : str, optional
            Save a screenshot of the image being represented. The image is
            stored in the path provided as an argument.
        use_trame : bool, optional
            Enables/disables the usage of the trame web visualizer. Defaults to the
            global setting ``USE_TRAME``.
        **plotting_options : dict, default: None
            Keyword arguments. For allowable keyword arguments, see the
            :func:`pyvista.Plotter.add_mesh` method.

        Examples
        --------
        Extrude a box centered at the origin to create rectangular body and
        plot it:

        >>> from ansys.geometry.core.misc.units import UNITS as u
        >>> from ansys.geometry.core.sketch import Sketch
        >>> from ansys.geometry.core.math import Plane, Point2D, Point3D, UnitVector3D
        >>> from ansys.geometry.core import Modeler
        >>> modeler = Modeler()
        >>> origin = Point3D([0, 0, 0])
        >>> plane = Plane(origin, direction_x=[1, 0, 0], direction_y=[0, 0, 1])
        >>> sketch = Sketch(plane)
        >>> box = sketch.box(Point2D([2, 0]), 4, 4)
        >>> design = modeler.create_design("my-design")
        >>> mycomp = design.add_component("my-comp")
        >>> body = mycomp.extrude_sketch("my-sketch", sketch, 1 * u.m)
        >>> body.plot()

        Plot the body and color each face individually:

        >>> body.plot(multi_colors=True)

        """
        return


class TemplateBody(IBody):
    """
    Represents solids and surfaces organized within the design assembly.

    Solids and surfaces synchronize to a design within a supporting Geometry service instance.

    Parameters
    ----------
    id : str
        Server-defined ID for the body.
    name : str
        User-defined label for the body.
    parent_component : Component
        Parent component to nest the new component under within the design assembly.
    grpc_client : GrpcClient
        An active supporting geometry service instance for design modeling.
    is_surface : bool, default: False
        Boolean indicating whether the ``TemplateBody`` is in fact a surface or an actual
        3D object (with volume).
    """

    def __init__(
        self,
        id: str,
        name: str,
        grpc_client: GrpcClient,
        is_surface: bool = False,
    ):
        """Constructor method for the ``TemplateBody`` class."""
        check_type(id, str)
        check_type(name, str)
        check_type(grpc_client, GrpcClient)
        check_type(is_surface, bool)

        self._id = id
        self._name = name
        self._grpc_client = grpc_client
        self._is_surface = is_surface
        self._surface_thickness = None
        self._surface_offset = None
        self._is_alive = True
        self._bodies_stub = BodiesStub(self._grpc_client.channel)
        self._commands_stub = CommandsStub(self._grpc_client.channel)
        self._tessellation = None

    def reset_tessellation_cache(func):
        """Decorator for ``TemplateBody`` methods that require a tessellation cache update.

        Parameters
        ----------
        func : method
            The method being called.

        Returns
        -------
        Any
            The output of the method, if any.
        """

        @wraps(func)
        def wrapper(self: "TemplateBody", *args, **kwargs):
            self._tessellation = None
            return func(self, *args, **kwargs)

        return wrapper

    @property
    def _grpc_id(self) -> EntityIdentifier:
        """gRPC entity identifier of this body."""
        return EntityIdentifier(id=self._id)

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_surface(self) -> bool:
        return self._is_surface

    @property
    def surface_thickness(self) -> Union[Quantity, None]:
        return self._surface_thickness if self.is_surface else None

    @property
    def surface_offset(self) -> Union["MidSurfaceOffsetType", None]:
        return self._surface_offset if self.is_surface else None

    @property
    @protect_grpc
    def faces(self) -> List[Face]:
        self._grpc_client.log.debug(f"Retrieving faces for body {self.id} from server.")
        grpc_faces = self._bodies_stub.GetFaces(self._grpc_id)
        return [
            Face(grpc_face.id, SurfaceType(grpc_face.surface_type), self, self._grpc_client)
            for grpc_face in grpc_faces.faces
        ]

    @property
    @protect_grpc
    def edges(self) -> List[Edge]:
        self._grpc_client.log.debug(f"Retrieving edges for body {self.id} from server.")
        grpc_edges = self._bodies_stub.GetEdges(self._grpc_id)
        return [
            Edge(grpc_edge.id, CurveType(grpc_edge.curve_type), self, self._grpc_client)
            for grpc_edge in grpc_edges.edges
        ]

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    @protect_grpc
    def volume(self) -> Quantity:
        if self.is_surface:
            self._grpc_client.log.debug("Dealing with planar surface. Returning 0 as the volume.")
            return Quantity(0, DEFAULT_UNITS.SERVER_VOLUME)
        else:
            self._grpc_client.log.debug(f"Retrieving volume for body {self.id} from server.")
            volume_response = self._bodies_stub.GetVolume(self._grpc_id)
            return Quantity(volume_response.volume, DEFAULT_UNITS.SERVER_VOLUME)

    @protect_grpc
    @check_input_types
    def assign_material(self, material: Material) -> None:
        self._grpc_client.log.debug(f"Assigning body {self.id} material {material.name}.")
        self._bodies_stub.SetAssignedMaterial(
            SetAssignedMaterialRequest(id=self._id, material=material.name)
        )

    @protect_grpc
    @check_input_types
    def add_midsurface_thickness(self, thickness: Quantity) -> None:
        if self.is_surface:
            self._commands_stub.AssignMidSurfaceThickness(
                AssignMidSurfaceThicknessRequest(
                    bodies_or_faces=[self.id], thickness=thickness.m_as(DEFAULT_UNITS.SERVER_LENGTH)
                )
            )
            self._surface_thickness = thickness
        else:
            self._grpc_client.log.warning(
                f"Body {self.name} cannot be assigned a mid-surface thickness since it is not a surface. Ignoring request."  # noqa : E501
            )

    @protect_grpc
    @check_input_types
    def add_midsurface_offset(self, offset: MidSurfaceOffsetType) -> None:
        if self.is_surface:
            self._commands_stub.AssignMidSurfaceOffsetType(
                AssignMidSurfaceOffsetTypeRequest(
                    bodies_or_faces=[self.id], offset_type=offset.value
                )
            )
            self._surface_offset = offset
        else:
            self._grpc_client.log.warning(
                f"Body {self.name} cannot be assigned a mid-surface offset since it is not a surface. Ignoring request."  # noqa : E501
            )

    @protect_grpc
    @check_input_types
    def imprint_curves(self, faces: List[Face], sketch: Sketch) -> Tuple[List[Edge], List[Face]]:
        # Verify that each of the faces provided are part of this body
        body_faces = self.faces
        for provided_face in faces:
            is_found = False
            for body_face in body_faces:
                if provided_face.id == body_face.id:
                    is_found = True
                    break
            if not is_found:
                raise ValueError(f"Face with id {provided_face.id} is not part of this body.")

        self._grpc_client.log.debug(
            f"Imprinting curves provided on {self.id} "
            + f"for faces {[face.id for face in faces]}."
        )

        imprint_response = self._commands_stub.ImprintCurves(
            ImprintCurvesRequest(
                body=self._id,
                curves=sketch_shapes_to_grpc_geometries(sketch._plane, sketch.edges, sketch.faces),
                faces=[face._id for face in faces],
            )
        )

        new_edges = [
            Edge(grpc_edge.id, grpc_edge.curve_type, self, self._grpc_client)
            for grpc_edge in imprint_response.edges
        ]

        new_faces = [
            Face(grpc_face.id, grpc_face.surface_type, self, self._grpc_client)
            for grpc_face in imprint_response.faces
        ]

        return (new_edges, new_faces)

    @protect_grpc
    @check_input_types
    def project_curves(
        self,
        direction: UnitVector3D,
        sketch: Sketch,
        closest_face: bool,
        only_one_curve: Optional[bool] = False,
    ) -> List[Face]:
        curves = sketch_shapes_to_grpc_geometries(
            sketch._plane, sketch.edges, sketch.faces, only_one_curve=only_one_curve
        )

        self._grpc_client.log.debug(f"Projecting provided curves on {self.id}.")

        project_response = self._commands_stub.ProjectCurves(
            ProjectCurvesRequest(
                body=self._id,
                curves=curves,
                direction=unit_vector_to_grpc_direction(direction),
                closest_face=closest_face,
            )
        )

        projected_faces = [
            Face(grpc_face.id, grpc_face.surface_type, self, self._grpc_client)
            for grpc_face in project_response.faces
        ]

        return projected_faces

    @protect_grpc
    @check_input_types
    @reset_tessellation_cache
    def translate(self, direction: UnitVector3D, distance: Union[Quantity, Distance, Real]) -> None:
        distance = distance if isinstance(distance, Distance) else Distance(distance)

        translation_magnitude = distance.value.m_as(DEFAULT_UNITS.SERVER_LENGTH)

        self._grpc_client.log.debug(f"Translating body {self.id}.")

        self._bodies_stub.Translate(
            TranslateRequest(
                ids=[self.id],
                direction=unit_vector_to_grpc_direction(direction),
                distance=translation_magnitude,
            )
        )

    @protect_grpc
    def copy(self, parent: "Component", name: str = None) -> "Body":
        from ansys.geometry.core.designer.component import Component

        # Check input types
        check_type(parent, Component)
        check_type(name, (type(None), str))
        copy_name = self.name if name is None else name

        self._grpc_client.log.debug(f"Copying body {self.id}.")

        # Perform copy request to server
        response = self._bodies_stub.Copy(
            CopyRequest(
                id=self.id,
                parent=parent.id,
                name=copy_name,
            )
        )

        # Assign the new body to its specified parent (and return the new body)
        tb = TemplateBody(
            response.master_id, copy_name, self._grpc_client, is_surface=self.is_surface
        )
        parent._transformed_part.part.bodies.append(tb)
        return Body(response.id, response.name, parent, tb)

    @protect_grpc
    def tessellate(
        self, merge: Optional[bool] = False, transform: Matrix44 = IDENTITY_MATRIX44
    ) -> Union["PolyData", "MultiBlock"]:
        # lazy import here to improve initial module load time
        import pyvista as pv

        if not self.is_alive:
            return pv.PolyData() if merge else pv.MultiBlock()

        self._grpc_client.log.debug(f"Requesting tessellation for body {self.id}.")

        # cache tessellation
        if not self._tessellation:
            resp = self._bodies_stub.GetTessellation(self._grpc_id)
            self._tessellation = resp.face_tessellation.values()

        pdata = [tess_to_pd(tess).transform(transform) for tess in self._tessellation]
        comp = pv.MultiBlock(pdata)
        if merge:
            ugrid = comp.combine()
            return pv.PolyData(ugrid.points, ugrid.cells, n_faces=ugrid.n_cells)
        return comp

    def plot(
        self,
        merge: bool = False,
        screenshot: Optional[str] = None,
        use_trame: Optional[bool] = None,
        **plotting_options: Optional[dict],
    ) -> None:
        # lazy import here to improve initial module load time

        from ansys.geometry.core.plotting import PlotterHelper

        pl_helper = PlotterHelper(use_trame=use_trame)
        pl = pl_helper.init_plotter()
        pl.add_body(self, merge=merge, **plotting_options)
        pl_helper.show_plotter(pl, screenshot=screenshot)

    def __repr__(self) -> str:
        """String representation of the body."""
        lines = [f"ansys.geometry.core.designer.TemplateBody {hex(id(self))}"]
        lines.append(f"  Name                 : {self.name}")
        lines.append(f"  Exists               : {self.is_alive}")
        lines.append(f"  Surface body         : {self.is_surface}")
        if self.is_surface:
            lines.append(f"  Surface thickness    : {self.surface_thickness}")
            lines.append(f"  Surface offset       : {self.surface_offset}")

        return "\n".join(lines)


class Body(IBody):
    """
    Represents solids and surfaces organized within the design assembly.

    Solids and surfaces synchronize to a design within a supporting Geometry service instance.

    Parameters
    ----------
    id : str
        Server-defined ID for the body.
    name : str
        User-defined label for the body.
    parent : Component
        Parent component to nest the new component under within the design assembly.
    template : TemplateBody
        The master body that this body is an occurrence of.
    """

    def __init__(self, id, name, parent: "Component", template: TemplateBody) -> None:
        """Constructor method for the ``Body`` class."""
        self._id = id
        self._name = name
        self._parent = parent
        self._template = template

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._template.name

    @property
    def parent(self) -> "Component":
        return self._parent

    @property
    @protect_grpc
    def faces(self) -> List[Face]:
        self._template._grpc_client.log.debug(f"Retrieving faces for body {self.id} from server.")
        grpc_faces = self._template._bodies_stub.GetFaces(EntityIdentifier(id=self.id))
        return [
            Face(
                grpc_face.id,
                SurfaceType(grpc_face.surface_type),
                self,
                self._template._grpc_client,
            )
            for grpc_face in grpc_faces.faces
        ]

    @property
    @protect_grpc
    def edges(self) -> List[Edge]:
        self._template._grpc_client.log.debug(f"Retrieving edges for body {self.id} from server.")
        grpc_edges = self._template._bodies_stub.GetEdges(EntityIdentifier(id=self.id))
        return [
            Edge(grpc_edge.id, CurveType(grpc_edge.curve_type), self, self._template._grpc_client)
            for grpc_edge in grpc_edges.edges
        ]

    @property
    def _is_alive(self) -> bool:
        return self._template.is_alive

    @_is_alive.setter
    def _is_alive(self, value: bool):
        self._template._is_alive = value

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    def is_surface(self) -> bool:
        return self._template.is_surface

    @property
    def _surface_thickness(self) -> Union[Quantity, None]:
        return self._template.surface_thickness

    @_surface_thickness.setter
    def _surface_thickness(self, value):
        self._template._surface_thickness = value

    @property
    def surface_thickness(self) -> Union[Quantity, None]:
        return self._surface_thickness

    @property
    def _surface_offset(self) -> Union["MidSurfaceOffsetType", None]:
        return self._template._surface_offset

    @_surface_offset.setter
    def _surface_offset(self, value: "MidSurfaceOffsetType"):
        self._template._surface_offset = value

    @property
    def surface_offset(self) -> Union["MidSurfaceOffsetType", None]:
        return self._surface_offset

    @property
    def volume(self) -> Quantity:
        return self._template.volume

    def assign_material(self, material: Material) -> None:
        self._template.assign_material(material)

    def add_midsurface_thickness(self, thickness: Quantity) -> None:
        self._template.add_midsurface_thickness(thickness)

    def add_midsurface_offset(self, offset: "MidSurfaceOffsetType") -> None:
        self._template.add_midsurface_offset(offset)

    def imprint_curves(self, faces: List[Face], sketch: Sketch) -> Tuple[List[Edge], List[Face]]:
        return self._template.imprint_curves(faces, sketch)

    def project_curves(
        self,
        direction: UnitVector3D,
        sketch: Sketch,
        closest_face: bool,
        only_one_curve: Optional[bool] = False,
    ) -> List[Face]:
        return self._template.project_curves(direction, sketch, closest_face, only_one_curve)

    def translate(self, direction: UnitVector3D, distance: Union[Quantity, Distance, Real]) -> None:
        return self._template.translate(direction, distance)

    def copy(self, parent: "Component", name: str = None) -> "Body":
        return self._template.copy(parent, name)

    def tessellate(self, merge: Optional[bool] = False) -> Union["PolyData", "MultiBlock"]:
        return self._template.tessellate(merge, self.parent.get_world_transform())

    def plot(
        self,
        merge: bool = False,
        screenshot: Optional[str] = None,
        use_trame: Optional[bool] = None,
        **plotting_options: Optional[dict],
    ) -> None:
        return self._template.plot(merge, screenshot, use_trame, **plotting_options)

    def __repr__(self) -> str:
        """String representation of the body."""
        lines = [f"ansys.geometry.core.designer.Body {hex(id(self))}"]
        lines.append(f"  Name                 : {self.name}")
        lines.append(f"  Exists               : {self.is_alive}")
        lines.append(f"  Parent component     : {self._parent.name}")
        lines.append(f"  TemplateBody         : {self._template.id}")
        lines.append(f"  Surface body         : {self.is_surface}")
        if self.is_surface:
            lines.append(f"  Surface thickness    : {self.surface_thickness}")
            lines.append(f"  Surface offset       : {self.surface_offset}")

        return "\n".join(lines)
