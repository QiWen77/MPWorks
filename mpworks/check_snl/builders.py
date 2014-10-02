import sys
from mpworks.snl_utils.mpsnl import MPStructureNL, SNLGroup
from pymatgen.analysis.structure_matcher import StructureMatcher, ElementComparator
from matgendb.builders.core import Builder
from matgendb.builders.util import get_builder_log

_log = get_builder_log("cross_checker")

class SNLGroupCrossChecker(Builder):
    """cross-check all SNL Groups via StructureMatcher.fit of their canonical SNLs"""
    def __init__(self, *args, **kwargs):
        self._matcher = StructureMatcher(
            ltol=0.2, stol=0.3, angle_tol=5, primitive_cell=True, scale=True,
            attempt_supercell=False, comparator=ElementComparator()
        )
        Builder.__init__(self, *args, **kwargs)

    def get_items(self, snlgroups=None):
        """iterator over same-composition groups of SNLGroups rev-sorted by size

        :param snlgroups: 'snlgroups' collection in 'snl_mp_prod' DB
        :type snlgroups: QueryEngine
        """
        self._snlgroups = snlgroups
        pipeline = [ { '$limit': 1000 } ]
        group_expression = {
            '_id': '$reduced_cell_formula_abc',
            'num_snlgroups': { '$sum': 1 },
            'snlgroup_ids': { '$addToSet': "$snlgroup_id" }
        }
        pipeline.append({ '$group': group_expression })
        pipeline.append({ '$match': { 'num_snlgroups': { '$gt': 1 } } })
        pipeline.append({ '$sort': { 'num_snlgroups': -1 } })
        pipeline.append({ '$project': { 'snlgroup_ids': 1 } })
        return self._snlgroups.collection.aggregate(pipeline)['result']

    def process_item(self, item):
        """combine all SNL Groups for current composition (item)"""
        snlgroups = {} # keep {snlgroup_id: SNLGroup} to avoid dupe queries

        def _get_snl_group(gid):
            if gid not in snlgroups:
                try:
                    snlgrp_dict = self._snlgroups.collection.find_one({ "snlgroup_id": gid })
                    snlgroups[gid] = SNLGroup.from_dict(snlgrp_dict)
                except:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    _log.info(exc_type, exc_value)
                    return None # TODO: return error category
            return snlgroups[gid]

        for idx,primary_id in enumerate(item['snlgroup_ids'][:-1]):
            primary_group = _get_snl_group(primary_id)
            if primary_group is None: continue
            for secondary_id in item['snlgroup_ids'][idx+1:]:
                secondary_group = _get_snl_group(secondary_id)
                if secondary_group is None: continue
                is_match = self._matcher.fit(
                    primary_group.canonical_structure,
                    secondary_group.canonical_structure
                )
                _log.info('%d:%s, %d:%s = %r' % (
                    primary_id, primary_group.canonical_snl.snlgroup_key,
                    secondary_id, secondary_group.canonical_snl.snlgroup_key,
                    is_match
                ))
        _log.info(snlgroups.keys())
