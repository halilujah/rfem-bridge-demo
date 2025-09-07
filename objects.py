from dataclasses import dataclass, field
from typing import List, Tuple

# -----------------
# Bridge Parameters
# -----------------
# -----------------
# FEA Core Objects
# -----------------
@dataclass
class Node:
    id: int
    x: float
    y: float
    z: float

@dataclass
class Line:
    id: int
    node_start: int
    node_end: int
    type: str = "beam"  # can be beam, truss, plate
    section: str= ""

@dataclass
class Surface:
    id: int
    node_1: int
    node_2: int
    node_3: int
    node_4: int
    thickness: float

@dataclass
class Support:
    id: int
    node_ids: list[int]        # nodes where support is applied
    type: str = "pin"        # pinned, roller, fixed, etc.

class FEAModel:
    def __init__(self):
        self.nodes: dict[Tuple[float,float,float], Node] = {}
        self.lines: list[Line] = []
        self.surfaces: list[Surface] = []
        self.supports: list[Support] = []

        self.node_counter = 1
        self.line_counter = 1
        self.surface_counter = 1
        self.support_counter = 1

        self.flange_width: float
        self.flange_thickness: float
        self.max_deflection:float = None

    def add_support(self, node_ids: list[int], type="pin") -> Support:
        s = Support(self.support_counter, node_ids, type)
        self.supports.append(s)
        self.support_counter += 1
        return s
    
    def get_or_create_node(self, x, y, z) -> Node:
        key = (round(x,3), round(y,3), round(z,3))  # rounding avoids float duplicates
        if key in self.nodes:
            return self.nodes[key]
        node = Node(self.node_counter, x, y, z)
        self.nodes[key] = node
        self.node_counter += 1
        return node

    def add_line(self, n1: Node, n2: Node, type="beam", section="default") -> Line:
        line = Line(self.line_counter, n1.id, n2.id, type, section)
        self.lines.append(line)
        self.line_counter += 1
        return line

    def add_surface(self, n1: Node, n2: Node, n3: Node, n4: Node, thickness: float) -> Surface:
        surface = Surface(self.surface_counter, n1.id, n2.id, n3.id, n4.id, thickness)
        self.surfaces.append(surface)
        self.surface_counter += 1
        return surface
      
@dataclass
class Girder:
    id: int
    depth: float
    flange_width: float
    flange_thickness: float
    web_thickness: float
    x: float
    fea_lines: list[Line] = field(default_factory=list)
    fea_surfaces: list[Surface] = field(default_factory=list)

    def generate_fea(self, fea: FEAModel, stations: list[float]):
        """Mesh girder along given station positions (aligned with deck mesh)."""
        for j in range(len(stations)-1):
            xa, xb = stations[j], stations[j+1]

            # top nodes
            n1 = fea.get_or_create_node(xa, self.x, self.depth)
            n2 = fea.get_or_create_node(xb, self.x, self.depth)

            # bottom nodes
            n3 = fea.get_or_create_node(xa, self.x, 0)
            n4 = fea.get_or_create_node(xb, self.x, 0)

            # flange lines
            self.fea_lines.append(fea.add_line(n1, n2, "beam", "top_flange"))
            self.fea_lines.append(fea.add_line(n3, n4, "beam", "bottom_flange"))

            # web surface between top and bottom
            self.fea_surfaces.append(fea.add_surface(n1, n2, n4, n3, self.web_thickness))

@dataclass
class Deck:
    thickness: float
    overhang: float
    fea_surfaces: list[Surface] = field(default_factory=list)

    def generate_fea(self, fea: FEAModel, girders: list[Girder], 
                     x_start: float, x_end: float, 
                     crossframes: list[float], mesh_size: float):

        # Generate mesh stations along span
        stations = generate_stations(x_start, x_end, crossframes, mesh_size)

        # Lateral positions: overhang left → girders → overhang right
        girder_positions = [g.x for g in girders]
        y_positions = [min(girder_positions) - self.overhang] + girder_positions + [max(girder_positions) + self.overhang]

        # Loop through girder bays (including overhang bays)
        for i in range(len(y_positions)-1):
            y1, y2 = y_positions[i], y_positions[i+1]

            for j in range(len(stations)-1):
                xa, xb = stations[j], stations[j+1]

                # Quad panel nodes
                n1 = fea.get_or_create_node(xa, y1, girders[0].depth)
                n2 = fea.get_or_create_node(xb, y1, girders[0].depth)
                n3 = fea.get_or_create_node(xb, y2, girders[0].depth)
                n4 = fea.get_or_create_node(xa, y2, girders[0].depth)

                self.fea_surfaces.append(fea.add_surface(n1,n2,n3,n4,self.thickness))


@dataclass
class CrossFrame:
    id: int
    station: float
    type: str = "K"
    fea_lines: list[Line] = field(default_factory=list)
    g1:Girder = None
    g2:Girder = None


    def generate_fea(self, fea: FEAModel):
        # top + bottom nodes at given x_pos
        n1 = fea.get_or_create_node(self.station, self.g1.x, self.g1.depth)
        n2 = fea.get_or_create_node(self.station, self.g2.x, self.g2.depth)
        n3 = fea.get_or_create_node(self.station, self.g1.x, 0)
        n4 = fea.get_or_create_node(self.station, self.g2.x, 0)

        # K frame: diagonals (n1→n4, n3→n2) + horizontals (n1→n3, n2→n4)
        self.fea_lines.append(fea.add_line(n1,n4,"truss","crossframe"))
        self.fea_lines.append(fea.add_line(n3,n2,"truss","crossframe"))
        self.fea_lines.append(fea.add_line(n1,n3,"beam","crossframe"))
        self.fea_lines.append(fea.add_line(n2,n4,"beam","crossframe"))


def generate_stations(x_start: float, x_end: float, crossframes: list[float], mesh_size: float) -> list[float]:
    """Generate mesh stations along the span."""
    stations = [x_start, x_end] + crossframes
    stations = sorted(set(stations))  # unique + sorted

    refined = []
    for i in range(len(stations)-1):
        a, b = stations[i], stations[i+1]
        length = b - a
        n_div = max(1, int(round(length / mesh_size)))
        dx = length / n_div
        for j in range(n_div):
            refined.append(a + j*dx)
    refined.append(x_end)

    return sorted(set(refined))


def generate_supports(self,girders: list[Girder], span_lengths: list[float], support_type="fixed"):
    x_positions = [0]
    x_acc = 0
    for L in span_lengths:
        x_acc += L
        x_positions.append(x_acc)
    for x in x_positions:
        for g in girders:
            # bottom flange node at this span boundary
            n = self.get_or_create_node(x, g.x, 0)
            self.add_support([n.id], support_type)