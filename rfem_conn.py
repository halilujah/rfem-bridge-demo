from dlubal.api import rfem
from matplotlib.pylab import inf

from config import RFEM_KEY
from objects import FEAModel

api_key = RFEM_KEY

def fea_to_rfem(fea: FEAModel, model_name="bridge_model"):
    with rfem.Application(api_key_value=api_key) as rfem_app:
        rfem_app.create_model(name=model_name)
        rfem_app.delete_all_objects()
        lst = []

        # Materials
        steel = rfem.structure_core.Material(no=1, name="S450 | EN 1993-1-1:2005-05")
        conc  = rfem.structure_core.Material(no=2, name="C30/37 | EN 1992-1-1:2004-11")
        lst += [steel, conc]

        # Sections
        lst.append(rfem.structure_core.Section(no=1, material=1, name=f"R_M1 {fea.flange_width}/{fea.flange_thickness}"))   # girders
        lst.append(rfem.structure_core.Section(no=2, material=1, name="L 100x10"))  # cross-frames

        # Nodes
        for n in fea.nodes.values():
            lst.append(rfem.structure_core.Node(
                no=n.id, coordinate_1=n.x, coordinate_2=n.y, coordinate_3=-n.z
            ))

        # Lines (from FE model)
        for l in fea.lines:
            lst.append(rfem.structure_core.Line(
                no=l.id, definition_nodes=[l.node_start, l.node_end]
            ))

        # Members
        for l in fea.lines:
            if "flange" in l.section:  # girders
                lst.append(rfem.structure_core.Member(
                    no=1000+l.id, line=l.id, section_start=1
                ))
            elif "crossframe" in l.section:  # cross-frames
                lst.append(rfem.structure_core.Member(
                    no=2000+l.id, line=l.id, section_start=2,
                    type=rfem.structure_core.Member.TYPE_TRUSS
                ))

        # Surfaces (deck panels)
        surface_no = 1
        line_no = 10000
        for s in fea.surfaces:
            nids = [s.node_1, s.node_2, s.node_3, s.node_4]
            b_lines = []
            for i in range(4):
                n_start, n_end = nids[i], nids[(i+1)%4]
                lst.append(rfem.structure_core.Line(no=line_no, definition_nodes=[n_start, n_end]))
                b_lines.append(line_no)
                line_no += 1
            lst.append(rfem.structure_core.Surface(no=surface_no, boundary_lines=b_lines))
            surface_no += 1

        # Thickness (applied to all deck surfaces)
        lst.append(
            rfem.structure_core.Thickness(
                no=1,
                material=2,
                uniform_thickness=fea.surfaces[0].thickness if fea.surfaces else 0.25,
                assigned_to_surfaces=list(range(1, surface_no))
            )
        )

        # Supports
        for s in fea.supports:
            lst.append(
                rfem.types_for_nodes.NodalSupport(
                    no=s.id,
                    nodes=s.node_ids,
                    spring_x=inf, spring_y=inf, spring_z=inf
                )
            )

        lst.append(rfem.loading.StaticAnalysisSettings(
            no=1))
        
        lst.append(rfem.loading.LoadCase(
            no=1,
            name="Self weight",
            static_analysis_settings=1))
        
        
        # Create objects & run
        rfem_app.create_object_list(lst)
        rfem_app.calculate_all(skip_warnings=True)
        results_grid_df = rfem_app.get_results(
            results_type=rfem.results.STATIC_ANALYSIS_NODES_GLOBAL_DEFORMATIONS,
        ).data
        fea.max_deflection = results_grid_df["u_abs"].max()
        print(results_grid_df)
        print("✅ Bridge model exported and solved in RFEM")
