
## for Surface Energy Calculation
from __future__ import division, unicode_literals
__author__ = "Richard Tran"
__version__ = "0.1"
__email__ = "rit634989@gmail.com"
__date__ = "6/24/15"

import os
from pymongo import MongoClient
from pymatgen.core.metal_slab import MPSlabVaspInputSet
from mpworks.firetasks.surface_tasks import RunCustodianTask, \
    VaspDBInsertTask, WriteVaspInputs
from custodian.vasp.jobs import VaspJob
from pymatgen.core.surface import generate_all_slabs, SlabGenerator
from pymatgen.io.vaspio_set import MPVaspInputSet, DictVaspInputSet
from pymatgen.core.surface import Slab, SlabGenerator, generate_all_slabs
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.matproj.rest import MPRester

import os
from pymongo import MongoClient
from fireworks.core.firework import Firework, Workflow
from fireworks.core.launchpad import LaunchPad

from pymatgen import write_structure
from pymatgen.io.smartio import CifParser
from matgendb import QueryEngine


def create_surface_workflows(max_index, api_key, list_of_elements,
                             list_of_indices=None,
                             k_product=50, max_normal_search=False, host=None, port=None,
                             user=None, password=None, database=None,
                             symprec=0.001, angle_tolerance=5,
                             job=VaspJob(["mpirun", "-n", "16", "vasp"]),
                             launchpad_dir="", consider_term=False):

    launchpad = LaunchPad.from_file(os.path.join(os.environ["HOME"],
                                                 launchpad_dir,
                                                 "my_launchpad.yaml"))
    launchpad.reset('', require_password=False)

    cust_params = {"custodian_params":
                       {"scratch_dir":
                            os.path.join("/global/scratch2/sd/",
                                         os.environ["USER"])},
                   "jobs": job}

    fws=[]
    miller_index_dict = {}
    unit_cells = {}
    for el in list_of_elements:

        """
        element: str, element name of Metal
        miller_index: hkl, e.g. [1, 1, 0]
        api_key: to get access to MP DB
        """
        # This initializes the REST adaptor. Put your own API key in.
        # e.g. MPRester("QMt7nBdIioOVySW2")
        mprest = MPRester(api_key)
        #first is the lowest energy one
        prim_unit_cell = mprest.get_structures(el)[0]
        spa = SpacegroupAnalyzer(prim_unit_cell, symprec=symprec,
                                 angle_tolerance=angle_tolerance)
        conv_unit_cell = spa.get_conventional_standard_structure()
        unit_cells[el] = conv_unit_cell

        print el
        if max_normal_search:
            max_norm=max_index
        else: max_norm=None

        if list_of_indices:
            list_of_slabs = [SlabGenerator(conv_unit_cell, mill, 10, 10,
                                           max_normal_search=max(mill)).get_slab()
                             for mill in list_of_indices]
        else:
            list_of_slabs = generate_all_slabs(conv_unit_cell, max_index,
                                               10, 10, max_normal_search=max_norm)

        if not consider_term:
            list_miller=[]
            unique_slabs=[]
            for i, slab in enumerate(list_of_slabs):
                if slab.miller_index not in list_miller:
                    list_miller.append(slab.miller_index)
                    unique_slabs.append(slab)
        else:
            list_miller=[slab.miller_index for slab in list_of_slabs]

        miller_index_dict[el] = list_miller
        list_of_slabs = unique_slabs[:]
        # return miller_index_dict later to be used for energy analysis  and wulff construction

        ocwd = os.getcwd()
        for slab in list_of_slabs:


            miller_index=slab.miller_index
            print miller_index

            surface_area = slab.surface_area

            vaspdbinsert_params = {'host': host,
                                   'port': port, 'user': user,
                                   'password': password,
                                   'database': database,
                                   'collection': "Surface_Calculations",
                                   'miller_index': miller_index}

            folderbulk = '/%s_%s_k%s_%s%s%s' %(slab[0].specie, 'bulk', k_product,
                                              str(miller_index[0]),
                                              str(miller_index[1]),
                                              str(miller_index[2]))
            folderslab = folderbulk.replace('bulk', 'slab')

            fw = Firework([WriteVaspInputs(slab=slab,
                                           folder=ocwd+folderbulk),
                           RunCustodianTask(dir=ocwd+folderbulk, **cust_params),
                           VaspDBInsertTask(struct_type="oriented_unit_cell",
                                            loc=ocwd+folderbulk,
                                            **vaspdbinsert_params),
                           WriteVaspInputs(slab=slab,
                                           folder=ocwd+folderslab, bulk=False),
                           RunCustodianTask(dir=ocwd+folderslab, **cust_params),
                           VaspDBInsertTask(struct_type="slab_cell",
                                            loc=ocwd+folderslab,
                                            surface_area=surface_area,
                                            **vaspdbinsert_params)])

            fws.append(fw)
    wf = Workflow(fws, name="surface_calculation")
    launchpad.add_wf(wf)


# # Will become a class method of CreateSurfaceWorkflows later
# def EnergyAndWulff(list_of_elements, miller_indices, host=None, port=None, user=None, password=None, database=None):
#
# # The miller_indices are obtained from the
# # CreateSurfaceWorkflows as a returned list
# # of miller indices corresponding to a system
#
#     db_params = {'host': host, 'port': port,
#                  'database': database,
#                  'user': user, 'password': password}
#     qe = QueryEngine(collection='Surface_Calculations', **db_params)
#
#     optional_data = ["chemsys", "surface_area", "nsites"
#                      "structure_type", "miller_index"]
#
#     to_Jperm2 = 16.0217656
#     wulffshapes = {}
#     surface_energies = {}
#
#     for el in list_of_elements:
#
#         miller_list = self.miller_index_dict[el]
#         e_surf_list = []
#
#         for miller_index in miller_list:
#
#             slab_criteria = {'chemsys':el,
#                              'structure_type': 'slab_cell',
#                              'miller_index': miller_index}
#             unit_criteria = {'chemsys':el,
#                              'structure_type': 'oriented_unit_cell',
#                              'miller_index': miller_index}
#
#             slab_entry = qe.get_entries(slab_criteria, optional_data=optional_data)
#             oriented_ucell_entry = qe.get_entries(unit_criteria, optional_data=optional_data)
#
#             slabE = slab_entry.uncorrected_energy
#             bulkE = oriented_ucell_entry.energy_per_atom*slab_entry.data['nsites']
#             area = slab_entry.data['surface_area']
#
#             e_surf_list.append(((slabE-bulkE)/(2*area))*to_Jperm2)
#
#         wulffshapes[el] = wulff_3d(unitcell, miller_list, e_surf_list)
#         se_dict = {}
#         for i, hkl in enumerate(miller_list):
#             se_dict[str(hkl)] = e_surf_list[i]
#         surface_energies[el] = se_dict
#
#         return wulffshapes, surface_energies