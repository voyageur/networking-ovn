#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from ovsdbapp.backend.ovs_idl import command
from ovsdbapp.backend.ovs_idl import idlutils

from networking_ovn._i18n import _
from networking_ovn.common import utils


def _addvalue_to_list(row, column, new_value):
    row.addvalue(column, new_value)


def _delvalue_from_list(row, column, old_value):
    row.delvalue(column, old_value)


def _updatevalues_in_list(row, column, new_values=None, old_values=None):
    new_values = new_values or []
    old_values = old_values or []

    for new_value in new_values:
        row.addvalue(column, new_value)
    for old_value in old_values:
        row.delvalue(column, old_value)


def get_lsp_dhcp_options_uuids(lsp, lsp_name):
    # Get dhcpv4_options and dhcpv6_options uuids from Logical_Switch_Port,
    # which are references of port dhcp options in DHCP_Options table.
    uuids = set()
    for dhcp_opts in getattr(lsp, 'dhcpv4_options', []):
        external_ids = getattr(dhcp_opts, 'external_ids', {})
        if external_ids.get('port_id') == lsp_name:
            uuids.add(dhcp_opts.uuid)
    for dhcp_opts in getattr(lsp, 'dhcpv6_options', []):
        external_ids = getattr(dhcp_opts, 'external_ids', {})
        if external_ids.get('port_id') == lsp_name:
            uuids.add(dhcp_opts.uuid)
    return uuids


class AddLSwitchCommand(command.BaseCommand):
    def __init__(self, api, name, may_exist, **columns):
        super(AddLSwitchCommand, self).__init__(api)
        self.name = name
        self.columns = columns
        self.may_exist = may_exist

    def run_idl(self, txn):
        if self.may_exist:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.name, None)
            if lswitch:
                return
        row = txn.insert(self.api._tables['Logical_Switch'])
        row.name = self.name
        for col, val in self.columns.items():
            setattr(row, col, val)
        self.result = row.uuid

    def post_commit(self, txn):
        self.result = txn.get_insert_uuid(self.result)


class DelLSwitchCommand(command.BaseCommand):
    def __init__(self, api, name, if_exists):
        super(DelLSwitchCommand, self).__init__(api)
        self.name = name
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Switch %s does not exist") % self.name
            raise RuntimeError(msg)

        self.api._tables['Logical_Switch'].rows[lswitch.uuid].delete()


class LSwitchSetExternalIdCommand(command.BaseCommand):
    def __init__(self, api, name, field, value, if_exists):
        super(LSwitchSetExternalIdCommand, self).__init__(api)
        self.name = name
        self.field = field
        self.value = value
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.name)

        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Switch %s does not exist") % self.name
            raise RuntimeError(msg)

        lswitch.verify('external_ids')

        external_ids = getattr(lswitch, 'external_ids', {})
        external_ids[self.field] = self.value
        lswitch.external_ids = external_ids


class AddLPortChainCommand(command.BaseCommand):
    def __init__(self, api, lswitch, lport_chain, may_exist, **columns):
        super(AddLPortChainCommand, self).__init__(api)
        self.lport_chain = lport_chain
        self.lswitch = lswitch
        self.may_exist = may_exist
        self.columns = columns

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
            port_chains = getattr(lswitch, 'port_chains', [])

        except idlutils.RowNotFound:
            msg = _("Logical Switch %s does not exist") % self.lswitch
            raise RuntimeError(msg)
        if self.may_exist:
            port_chain = idlutils.row_by_value(self.api.idl,
                                               'Logical_Port_Chain', 'name',
                                               self.lport_chain, None)
            if port_chain:
                return
        lswitch.verify('port_chains')
        port_chain = txn.insert(self.api._tables['Logical_Port_Chain'])
        port_chain.name = self.lport_chain
        for col, val in self.columns.items():
            setattr(port_chain, col, val)
        port_chains.append(port_chain.uuid)
        setattr(lswitch, 'port_chains', port_chains)


class DelLPortChainCommand(command.BaseCommand):
    def __init__(self, api, lswitch, lport_chain, if_exists):
        super(DelLPortChainCommand, self).__init__(api)
        self.lswitch = lswitch
        self.lport_chain = lport_chain
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lport_chain = idlutils.row_by_value(self.api.idl,
                                                'Logical_Port_Chain',
                                                'name', self.lport_chain)
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
            port_chains = getattr(lswitch, 'port_chains', [])
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Port Chain %s does not exist") % self.lport_chain
            raise RuntimeError(msg)
        lswitch.verify('port_chains')

        port_chains.remove(lport_chain)
        setattr(lswitch, 'port_chains', port_chains)
        self.api._tables['Logical_Port_Chain'].rows[lport_chain.uuid].delete()


class SetLogicalPortChainCommand(command.BaseCommand):
    def __init__(self, api, lport_chain, if_exists, **columns):
        super(SetLogicalPortChainCommand, self).__init__(api)
        self.lport_chain = lport_chain
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lport_chain = idlutils.row_by_value(self.api.idl,
                                                'Logical_Port_Chain',
                                                'name', self.lport_chain)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Port Chain %s does not exist") % self.lport_chain
            raise RuntimeError(msg)

        for col, val in self.columns.items():
            setattr(lport_chain, col, val)


class AddLogicalPortPairGroupCommand(command.BaseCommand):
    def __init__(self, api, lport_pair_group, lport_chain, may_exist,
                 **columns):
        super(AddLogicalPortPairGroupCommand, self).__init__(api)
        self.lport_pair_group = lport_pair_group
        self.lport_chain = lport_chain
        self.may_exist = may_exist
        self.columns = columns

    def run_idl(self, txn):
        try:
            lport_chain = idlutils.row_by_value(self.api.idl,
                                                'Logical_Port_Chain',
                                                'name', self.lport_chain)
            port_pair_groups = getattr(lport_chain,
                                       'port_pair_groups', [])
        except idlutils.RowNotFound:
            msg = _("Logical Port Chain %s does not exist") % self.lport_chain
            raise RuntimeError(msg)
        if self.may_exist:
            port_pair_group = idlutils.row_by_value(
                self.api.idl, 'Logical_Port_Pair_Group', 'name',
                self.lport_pair_group, None)
            if port_pair_group:
                return

        lport_chain.verify('port_pair_groups')

        port_pair_group = txn.insert(
            self.api._tables['Logical_Port_Pair_Group'])
        port_pair_group.name = self.lport_pair_group
        for col, val in self.columns.items():
            setattr(port_pair_group, col, val)
        # add the newly created port_pair to existing lswitch
        port_pair_groups.append(port_pair_group.uuid)
        setattr(lport_chain, 'port_pair_groups', port_pair_groups)


class SetLogicalPortPairGroupCommand(command.BaseCommand):
    def __init__(self, api, lport_pair_group, if_exists, **columns):
        super(SetLogicalPortPairGroupCommand, self).__init__(api)
        self.lport_pair_group = lport_pair_group
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            port_pair_group = idlutils.row_by_value(
                self.api.idl, 'Logical_Port_Pair_Group',
                'name', self.lport_pair_group)
            port_pairs = getattr(self.lport_pair_group, 'port_pairs', [])
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Port Pair Group %s does not exist") % \
                self.lport_pair_group
            raise RuntimeError(msg)

        for col, val in self.columns.items():
            setattr(port_pair_group, col, val)


class DelLogicalPortPairGroupCommand(command.BaseCommand):
    def __init__(self, api, lport_pair_group, lport_chain, if_exists):
        super(DelLogicalPortPairGroupCommand, self).__init__(api)
        self.lport_pair_group = lport_pair_group
        self.lport_chain = lport_chain
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lport_pair_group = idlutils.row_by_value(
                self.api.idl, 'Logical_Port_Pair_Group',
                'name', self.lport_pair_group)
            lport_chain = idlutils.row_by_value(self.api.idl,
                                                'Logical_Port_Chain',
                                                'name', self.lport_chain)
            port_pair_groups = getattr(lport_chain, 'port_pair_groups', [])
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Port Pair Group %s does not exist") % \
                self.lport_pair_group
            raise RuntimeError(msg)

        lport_chain.verify('port_pair_groups')

        port_pair_groups.remove(lport_pair_group)
        setattr(lport_chain, 'port_pair_groups', port_pair_groups)
        self.api._tables['Logical_Port_Pair_Group'].\
            rows[lport_pair_group.uuid].delete()



class AddLSwitchPortCommand(command.BaseCommand):
    def __init__(self, api, lport, lswitch, may_exist, **columns):
        super(AddLSwitchPortCommand, self).__init__(api)
        self.lport = lport
        self.lswitch = lswitch
        self.may_exist = may_exist
        self.columns = columns

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
        except idlutils.RowNotFound:
            msg = _("Logical Switch %s does not exist") % self.lswitch
            raise RuntimeError(msg)
        if self.may_exist:
            port = idlutils.row_by_value(self.api.idl,
                                         'Logical_Switch_Port', 'name',
                                         self.lport, None)
            if port:
                return

        port = txn.insert(self.api._tables['Logical_Switch_Port'])
        port.name = self.lport
        dhcpv4_options = self.columns.pop('dhcpv4_options', [])
        if isinstance(dhcpv4_options, list):
            port.dhcpv4_options = dhcpv4_options
        else:
            port.dhcpv4_options = [dhcpv4_options.result]
        dhcpv6_options = self.columns.pop('dhcpv6_options', [])
        if isinstance(dhcpv6_options, list):
            port.dhcpv6_options = dhcpv6_options
        else:
            port.dhcpv6_options = [dhcpv6_options.result]
        for col, val in self.columns.items():
            setattr(port, col, val)
        # add the newly created port to existing lswitch
        _addvalue_to_list(lswitch, 'ports', port.uuid)
        self.result = port.uuid

    def post_commit(self, txn):
        self.result = txn.get_insert_uuid(self.result)


class SetLSwitchPortCommand(command.BaseCommand):
    def __init__(self, api, lport, if_exists, **columns):
        super(SetLSwitchPortCommand, self).__init__(api)
        self.lport = lport
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            port = idlutils.row_by_value(self.api.idl, 'Logical_Switch_Port',
                                         'name', self.lport)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Switch Port %s does not exist") % self.lport
            raise RuntimeError(msg)

        # Delete DHCP_Options records no longer refered by this port.
        # The table rows should be consistent for the same transaction.
        # After we get DHCP_Options rows uuids from port dhcpv4_options
        # and dhcpv6_options references, the rows shouldn't disappear for
        # this transaction before we delete it.
        cur_port_dhcp_opts = get_lsp_dhcp_options_uuids(
            port, self.lport)
        new_port_dhcp_opts = set()
        dhcpv4_options = self.columns.pop('dhcpv4_options', None)
        if dhcpv4_options is None:
            new_port_dhcp_opts.update([option.uuid for option in
                                       getattr(port, 'dhcpv4_options', [])])
        elif isinstance(dhcpv4_options, list):
            new_port_dhcp_opts.update(dhcpv4_options)
            port.dhcpv4_options = dhcpv4_options
        else:
            new_port_dhcp_opts.add(dhcpv4_options.result)
            port.dhcpv4_options = [dhcpv4_options.result]
        dhcpv6_options = self.columns.pop('dhcpv6_options', None)
        if dhcpv6_options is None:
            new_port_dhcp_opts.update([option.uuid for option in
                                       getattr(port, 'dhcpv6_options', [])])
        elif isinstance(dhcpv6_options, list):
            new_port_dhcp_opts.update(dhcpv6_options)
            port.dhcpv6_options = dhcpv6_options
        else:
            new_port_dhcp_opts.add(dhcpv6_options.result)
            port.dhcpv6_options = [dhcpv6_options.result]
        for uuid in cur_port_dhcp_opts - new_port_dhcp_opts:
            self.api._tables['DHCP_Options'].rows[uuid].delete()

        for col, val in self.columns.items():
            setattr(port, col, val)


class DelLSwitchPortCommand(command.BaseCommand):
    def __init__(self, api, lport, lswitch, if_exists):
        super(DelLSwitchPortCommand, self).__init__(api)
        self.lport = lport
        self.lswitch = lswitch
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lport = idlutils.row_by_value(self.api.idl, 'Logical_Switch_Port',
                                          'name', self.lport)
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Port %s does not exist") % self.lport
            raise RuntimeError(msg)

        # Delete DHCP_Options records no longer refered by this port.
        cur_port_dhcp_opts = get_lsp_dhcp_options_uuids(
            lport, self.lport)
        for uuid in cur_port_dhcp_opts:
            self.api._tables['DHCP_Options'].rows[uuid].delete()

        _delvalue_from_list(lswitch, 'ports', lport)
        self.api._tables['Logical_Switch_Port'].rows[lport.uuid].delete()


class AddLogicalPortPairCommand(command.BaseCommand):
    def __init__(self, api, lport_pair, lswitch, may_exist, **columns):
        super(AddLogicalPortPairCommand, self).__init__(api)
        self.lport_pair = lport_pair
        self.lswitch = lswitch
        self.may_exist = may_exist
        self.columns = columns

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
            port_pairs = getattr(lswitch, 'port_pairs', [])
        except idlutils.RowNotFound:
            msg = _("Logical Switch %s does not exist") % self.lswitch
            raise RuntimeError(msg)
        if self.may_exist:
            port_pair = idlutils.row_by_value(self.api.idl,
                                              'Logical_Port_Pair', 'name',
                                              self.lport_pair, None)
            if port_pair:
                return

        lswitch.verify('port_pairs')

        port_pair = txn.insert(self.api._tables['Logical_Port_Pair'])
        port_pair.name = self.lport_pair
        for col, val in self.columns.items():
            setattr(port_pair, col, val)
        # add the newly created port_pair to existing lswitch
        port_pairs.append(port_pair.uuid)
        setattr(lswitch, 'port_pairs', port_pairs)


class SetLogicalPortPairCommand(command.BaseCommand):
    def __init__(self, api, lport_pair, if_exists, **columns):
        super(SetLogicalPortPairCommand, self).__init__(api)
        self.lport_pair = lport_pair
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            port_pair = idlutils.row_by_value(self.api.idl,
                                              'Logical_Port_Pair',
                                              'name', self.lport_pair)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Port Pair%s does not exist") % self.lport_pair
            raise RuntimeError(msg)

        for col, val in self.columns.items():
            setattr(port_pair, col, val)


class DelLogicalPortPairCommand(command.BaseCommand):
    def __init__(self, api, lport_pair, lswitch, lport_pair_group, if_exists):
        super(DelLogicalPortPairCommand, self).__init__(api)
        self.lport_pair = lport_pair
        self.lswitch = lswitch
        self.lport_pair_group = lport_pair_group
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lport_pair = idlutils.row_by_value(self.api.idl,
                                               'Logical_Port_Pair',
                                               'name', self.lport_pair)
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
            lppg = idlutils.row_by_value(self.api.idl,
                                         'Logical_Port_Pair_Group',
                                         'name', self.lport_pair_group) 
            port_pairs = getattr(lswitch, 'port_pairs', [])
            port_pairs_ppg = getattr(lppg, 'port_pairs', [])
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Port Pair %s does not exist") % self.lport_pair
            raise RuntimeError(msg)

        lswitch.verify('port_pairs')
        lppg.verify('port_pairs')

        port_pairs.remove(lport_pair)
        port_pairs_ppg.remove(lport_pair)
        setattr(lswitch, 'port_pairs', port_pairs)
        setattr(lppg, 'port_pairs', port_pairs_ppg)
        self.api._tables['Logical_Port_Pair'].rows[lport_pair.uuid].delete()


class AddLogicalFlowClassifierCommand(command.BaseCommand):
    def __init__(self, api, lport_chain, lflow_classifier, may_exist,
                 **columns):
        super(AddLogicalFlowClassifierCommand, self).__init__(api)
        self.lport_chain = lport_chain
        self.lflow_classifier = lflow_classifier
        self.may_exist = may_exist
        self.columns = columns

    def run_idl(self, txn):
        try:
            port_chain = idlutils.row_by_value(self.api.idl,
                                               'Logical_Port_Chain',
                                               'name', self.lport_chain)
            fc = getattr(port_chain, 'flow_classifier', [])
        except idlutils.RowNotFound:
            msg = _("Logical port chain %s does not exist") % self.lport_chain
            raise RuntimeError(msg)
        if self.may_exist:
            flow_classifier = idlutils.row_by_value(
                self.api.idl, 'Logical_Flow_Classifier', 'name',
                self.lflow_classifier, None)
            if flow_classifier:
                return
        port_chain.verify('flow_classifier')

        flow_classifier = txn.insert(
            self.api._tables['Logical_Flow_Classifier'])
        flow_classifier.name = self.lflow_classifier
        for col, val in self.columns.items():
            setattr(flow_classifier, col, val)
        # add the newly created flow_classifier to existing lswitch
        fc.append(flow_classifier.uuid)
        setattr(port_chain, 'flow_classifier', fc)


class SetLogicalFlowClassifierCommand(command.BaseCommand):
    def __init__(self, api, lflow_classifier, if_exists, **columns):
        super(SetLogicalFlowClassifierCommand, self).__init__(api)
        self.lflow_classifier = lflow_classifier
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            flow_classifier = idlutils.row_by_value(
                self.api.idl, 'Logical_Flow_Classifier',
                'name', self.lflow_classifier)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Flow Classifier %s does not exist") % \
                self.lflow_classifier
            raise RuntimeError(msg)

        for col, val in self.columns.items():
            setattr(flow_classifier, col, val)


class DelLogicalFlowClassifierCommand(command.BaseCommand):
    def __init__(self, api, lport_chain, lflow_classifier, if_exists):
        super(DelLogicalFlowClassifierCommand, self).__init__(api)
        self.lflow_classifier = lflow_classifier
        self.lport_chain = lport_chain
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lflow_classifier = idlutils.row_by_value(
                self.api.idl, 'Logical_Flow_Classifier',
                'name', self.lflow_classifier)
            port_chain = idlutils.row_by_value(self.api.idl,
                                               'Logical_Port_Chain',
                                               'name', self.lport_chain)
            flow_classifier = getattr(port_chain, 'flow_classifier', [])
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Flow Classifier %s does not exist") % \
                self.lflow_classifier
            raise RuntimeError(msg)

        port_chain.verify('flow_classifier')

        flow_classifier.remove(lflow_classifier)
        setattr(port_chain, 'flow_classifier', flow_classifier)
        self.api._tables['Logical_Flow_Classifier'].\
            rows[lflow_classifier.uuid].delete()



class AddLRouterCommand(command.BaseCommand):
    def __init__(self, api, name, may_exist, **columns):
        super(AddLRouterCommand, self).__init__(api)
        self.name = name
        self.columns = columns
        self.may_exist = may_exist

    def run_idl(self, txn):
        if self.may_exist:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.name, None)
            if lrouter:
                return

        row = txn.insert(self.api._tables['Logical_Router'])
        row.name = self.name
        for col, val in self.columns.items():
            setattr(row, col, val)


class UpdateLRouterCommand(command.BaseCommand):
    def __init__(self, api, name, if_exists, **columns):
        super(UpdateLRouterCommand, self).__init__(api)
        self.name = name
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.name, None)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router %s does not exist") % self.name
            raise RuntimeError(msg)

        if lrouter:
            for col, val in self.columns.items():
                setattr(lrouter, col, val)
            return


class DelLRouterCommand(command.BaseCommand):
    def __init__(self, api, name, if_exists):
        super(DelLRouterCommand, self).__init__(api)
        self.name = name
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router %s does not exist") % self.name
            raise RuntimeError(msg)

        self.api._tables['Logical_Router'].rows[lrouter.uuid].delete()


class AddLRouterPortCommand(command.BaseCommand):
    def __init__(self, api, name, lrouter, **columns):
        super(AddLRouterPortCommand, self).__init__(api)
        self.name = name
        self.lrouter = lrouter
        self.columns = columns

    def run_idl(self, txn):

        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)
        try:
            idlutils.row_by_value(self.api.idl, 'Logical_Router_Port',
                                  'name', self.name)
            # The LRP entry with certain name has already exist, raise an
            # exception to notice caller. It's caller's responsibility to
            # call UpdateLRouterPortCommand to get LRP entry processed
            # correctly.
            msg = _("Logical Router Port with name \"%s\" "
                    "already exists.") % self.name
            raise RuntimeError(msg)
        except idlutils.RowNotFound:
            lrouter_port = txn.insert(self.api._tables['Logical_Router_Port'])
            lrouter_port.name = self.name
            for col, val in self.columns.items():
                setattr(lrouter_port, col, val)
            _addvalue_to_list(lrouter, 'ports', lrouter_port)


class UpdateLRouterPortCommand(command.BaseCommand):
    def __init__(self, api, name, if_exists, **columns):
        super(UpdateLRouterPortCommand, self).__init__(api)
        self.name = name
        self.columns = columns
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter_port = idlutils.row_by_value(self.api.idl,
                                                 'Logical_Router_Port',
                                                 'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router Port %s does not exist") % self.name
            raise RuntimeError(msg)

        if lrouter_port:
            for col, val in self.columns.items():
                setattr(lrouter_port, col, val)
            return


class DelLRouterPortCommand(command.BaseCommand):
    def __init__(self, api, name, lrouter, if_exists):
        super(DelLRouterPortCommand, self).__init__(api)
        self.name = name
        self.lrouter = lrouter
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter_port = idlutils.row_by_value(self.api.idl,
                                                 'Logical_Router_Port',
                                                 'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router Port %s does not exist") % self.name
            raise RuntimeError(msg)
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        _delvalue_from_list(lrouter, 'ports', lrouter_port)


class SetLRouterPortInLSwitchPortCommand(command.BaseCommand):
    def __init__(self, api, lswitch_port, lrouter_port):
        super(SetLRouterPortInLSwitchPortCommand, self).__init__(api)
        self.lswitch_port = lswitch_port
        self.lrouter_port = lrouter_port

    def run_idl(self, txn):
        try:
            port = idlutils.row_by_value(self.api.idl, 'Logical_Switch_Port',
                                         'name', self.lswitch_port)
        except idlutils.RowNotFound:
            msg = _("Logical Switch Port %s does not "
                    "exist") % self.lswitch_port
            raise RuntimeError(msg)

        options = {'router-port': self.lrouter_port}
        setattr(port, 'options', options)
        setattr(port, 'type', 'router')
        setattr(port, 'addresses', 'router')


class AddACLCommand(command.BaseCommand):
    def __init__(self, api, lswitch, lport, **columns):
        super(AddACLCommand, self).__init__(api)
        self.lswitch = lswitch
        self.lport = lport
        self.columns = columns

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
        except idlutils.RowNotFound:
            msg = _("Logical Switch %s does not exist") % self.lswitch
            raise RuntimeError(msg)

        row = txn.insert(self.api._tables['ACL'])
        for col, val in self.columns.items():
            setattr(row, col, val)
        row.external_ids = {'neutron:lport': self.lport}
        _addvalue_to_list(lswitch, 'acls', row.uuid)


class DelACLCommand(command.BaseCommand):
    def __init__(self, api, lswitch, lport, if_exists):
        super(DelACLCommand, self).__init__(api)
        self.lswitch = lswitch
        self.lport = lport
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', self.lswitch)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Switch %s does not exist") % self.lswitch
            raise RuntimeError(msg)

        acls_to_del = []
        acls = getattr(lswitch, 'acls', [])
        for acl in acls:
            ext_ids = getattr(acl, 'external_ids', {})
            if ext_ids.get('neutron:lport') == self.lport:
                acls_to_del.append(acl)
        for acl in acls_to_del:
            acl.delete()
        _updatevalues_in_list(lswitch, 'acls', old_values=acls_to_del)


class UpdateACLsCommand(command.BaseCommand):
    def __init__(self, api, lswitch_names, port_list, acl_new_values_dict,
                 need_compare=True, is_add_acl=True):
        """This command updates the acl list for the logical switches

        @param lswitch_names: List of Logical Switch Names
        @type lswitch_names: []
        @param port_list: Iterator of List of Ports
        @type port_list: []
        @param acl_new_values_dict: Dictionary of acls indexed by port id
        @type acl_new_values_dict: {}
        @need_compare: If acl_new_values_dict needs be compared with existing
                       acls.
        @type: Boolean.
        @is_add_acl: If updating is caused by acl adding action.
        @type: Boolean.

        """
        super(UpdateACLsCommand, self).__init__(api)
        self.lswitch_names = lswitch_names
        self.port_list = port_list
        self.acl_new_values_dict = acl_new_values_dict
        self.need_compare = need_compare
        self.is_add_acl = is_add_acl

    def _acl_list_sub(self, acl_list1, acl_list2):
        """Compute the elements in acl_list1 but not in acl_list2.

        If acl_list1 and acl_list2 were sets, the result of this routine
        could be thought of as acl_list1 - acl_list2. Note that acl_list1
        and acl_list2 cannot actually be sets as they contain dictionary
        items i.e. set([{'a':1}) doesn't work.
        """
        acl_diff = []
        for acl in acl_list1:
            if acl not in acl_list2:
                acl_diff.append(acl)
        return acl_diff

    def _compute_acl_differences(self, port_list, acl_old_values_dict,
                                 acl_new_values_dict, acl_obj_dict):
        """Compute the difference between the new and old sets of acls

        @param port_list: Iterator of a List of ports
        @type port_list: []
        @param acl_old_values_dict: Dictionary of old acl values indexed
                                    by port id
        @param acl_new_values_dict: Dictionary of new acl values indexed
                                    by port id
        @param acl_obj_dict: Dictionary of acl objects indexed by the acl
                             value in string format.
        @var acl_del_objs_dict: Dictionary of acl objects to be deleted
                                indexed by the lswitch.
        @var acl_add_values_dict: Dictionary of acl values to be added
                                  indexed by the lswitch.
        @return: (acl_del_objs_dict, acl_add_values_dict)
        @rtype: ({}, {})
        """

        acl_del_objs_dict = {}
        acl_add_values_dict = {}
        for port in port_list:
            lswitch_name = port['network_id']
            acls_old = acl_old_values_dict.get(port['id'], [])
            acls_new = acl_new_values_dict.get(port['id'], [])
            acls_del = self._acl_list_sub(acls_old, acls_new)
            acls_add = self._acl_list_sub(acls_new, acls_old)
            acl_del_objs = acl_del_objs_dict.setdefault(lswitch_name, [])
            for acl in acls_del:
                acl_del_objs.append(acl_obj_dict[str(acl)])
            acl_add_values = acl_add_values_dict.setdefault(lswitch_name, [])
            for acl in acls_add:
                # Remove lport and lswitch columns
                del acl['lswitch']
                del acl['lport']
                acl_add_values.append(acl)
        return acl_del_objs_dict, acl_add_values_dict

    def _get_update_data_without_compare(self):
        lswitch_ovsdb_dict = {}
        for switch_name in self.lswitch_names:
            switch_name = utils.ovn_name(switch_name)
            lswitch = idlutils.row_by_value(self.api.idl, 'Logical_Switch',
                                            'name', switch_name)
            lswitch_ovsdb_dict[switch_name] = lswitch
        if self.is_add_acl:
            acl_add_values_dict = {}
            for port in self.port_list:
                switch_name = utils.ovn_name(port['network_id'])
                if switch_name not in acl_add_values_dict:
                    acl_add_values_dict[switch_name] = []
                if port['id'] in self.acl_new_values_dict:
                    acl_add_values_dict[switch_name].append(
                        self.acl_new_values_dict[port['id']])
            acl_del_objs_dict = {}
        else:
            acl_add_values_dict = {}
            acl_del_objs_dict = {}
            del_acl_matches = []
            for acl_dict in self.acl_new_values_dict.values():
                del_acl_matches.append(acl_dict['match'])
            for switch_name, lswitch in lswitch_ovsdb_dict.items():
                if switch_name not in acl_del_objs_dict:
                    acl_del_objs_dict[switch_name] = []
                acls = getattr(lswitch, 'acls', [])
                for acl in acls:
                    if getattr(acl, 'match') in del_acl_matches:
                        acl_del_objs_dict[switch_name].append(acl)
        return lswitch_ovsdb_dict, acl_del_objs_dict, acl_add_values_dict

    def run_idl(self, txn):

        if self.need_compare:
            # Get all relevant ACLs in 1 shot
            acl_values_dict, acl_obj_dict, lswitch_ovsdb_dict = \
                self.api.get_acls_for_lswitches(self.lswitch_names)

            # Compute the difference between the new and old set of ACLs
            acl_del_objs_dict, acl_add_values_dict = \
                self._compute_acl_differences(
                    self.port_list, acl_values_dict,
                    self.acl_new_values_dict, acl_obj_dict)
        else:
            lswitch_ovsdb_dict, acl_del_objs_dict, acl_add_values_dict = \
                self._get_update_data_without_compare()

        for lswitch_name, lswitch in lswitch_ovsdb_dict.items():
            acl_del_objs = acl_del_objs_dict.get(lswitch_name, [])
            acl_add_values = acl_add_values_dict.get(lswitch_name, [])

            # Continue if no ACLs to add or delete.
            if not acl_del_objs and not acl_add_values:
                continue

            # Delete old ACLs.
            if acl_del_objs:
                for acl_del_obj in acl_del_objs:
                    acl_del_obj.delete()

            # Add new ACLs.
            acl_add_objs = None
            if acl_add_values:
                acl_add_objs = []
                for acl_value in acl_add_values:
                    row = txn.insert(self.api._tables['ACL'])
                    for col, val in acl_value.items():
                        setattr(row, col, val)
                    acl_add_objs.append(row.uuid)

            # Update logical switch ACLs.
            _updatevalues_in_list(lswitch, 'acls',
                                  new_values=acl_add_objs,
                                  old_values=acl_del_objs)


class AddStaticRouteCommand(command.BaseCommand):
    def __init__(self, api, lrouter, **columns):
        super(AddStaticRouteCommand, self).__init__(api)
        self.lrouter = lrouter
        self.columns = columns

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        row = txn.insert(self.api._tables['Logical_Router_Static_Route'])
        for col, val in self.columns.items():
            setattr(row, col, val)
        _addvalue_to_list(lrouter, 'static_routes', row.uuid)


class DelStaticRouteCommand(command.BaseCommand):
    def __init__(self, api, lrouter, ip_prefix, nexthop, if_exists):
        super(DelStaticRouteCommand, self).__init__(api)
        self.lrouter = lrouter
        self.ip_prefix = ip_prefix
        self.nexthop = nexthop
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        static_routes = getattr(lrouter, 'static_routes', [])
        for route in static_routes:
            ip_prefix = getattr(route, 'ip_prefix', '')
            nexthop = getattr(route, 'nexthop', '')
            if self.ip_prefix == ip_prefix and self.nexthop == nexthop:
                _delvalue_from_list(lrouter, 'static_routes', route)
                route.delete()
                break


class AddAddrSetCommand(command.BaseCommand):
    def __init__(self, api, name, may_exist, **columns):
        super(AddAddrSetCommand, self).__init__(api)
        self.name = name
        self.columns = columns
        self.may_exist = may_exist

    def run_idl(self, txn):
        if self.may_exist:
            addrset = idlutils.row_by_value(self.api.idl, 'Address_Set',
                                            'name', self.name, None)
            if addrset:
                return
        row = txn.insert(self.api._tables['Address_Set'])
        row.name = self.name
        for col, val in self.columns.items():
            setattr(row, col, val)


class DelAddrSetCommand(command.BaseCommand):
    def __init__(self, api, name, if_exists):
        super(DelAddrSetCommand, self).__init__(api)
        self.name = name
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            addrset = idlutils.row_by_value(self.api.idl, 'Address_Set',
                                            'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Address set %s does not exist. "
                    "Can't delete.") % self.name
            raise RuntimeError(msg)

        self.api._tables['Address_Set'].rows[addrset.uuid].delete()


class UpdateAddrSetCommand(command.BaseCommand):
    def __init__(self, api, name, addrs_add, addrs_remove, if_exists):
        super(UpdateAddrSetCommand, self).__init__(api)
        self.name = name
        self.addrs_add = addrs_add
        self.addrs_remove = addrs_remove
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            addrset = idlutils.row_by_value(self.api.idl, 'Address_Set',
                                            'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Address set %s does not exist. "
                    "Can't update addresses") % self.name
            raise RuntimeError(msg)

        _updatevalues_in_list(
            addrset, 'addresses',
            new_values=self.addrs_add,
            old_values=self.addrs_remove)


class UpdateAddrSetExtIdsCommand(command.BaseCommand):
    def __init__(self, api, name, external_ids, if_exists):
        super(UpdateAddrSetExtIdsCommand, self).__init__(api)
        self.name = name
        self.external_ids = external_ids
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            addrset = idlutils.row_by_value(self.api.idl, 'Address_Set',
                                            'name', self.name)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Address set %s does not exist. "
                    "Can't update external IDs") % self.name
            raise RuntimeError(msg)

        addrset.verify('external_ids')
        addrset_external_ids = getattr(addrset, 'external_ids', {})
        for ext_id_key, ext_id_value in self.external_ids.items():
            addrset_external_ids[ext_id_key] = ext_id_value
        addrset.external_ids = addrset_external_ids


class AddDHCPOptionsCommand(command.BaseCommand):
    def __init__(self, api, subnet_id, port_id=None, may_exists=True,
                 **columns):
        super(AddDHCPOptionsCommand, self).__init__(api)
        self.columns = columns
        self.may_exists = may_exists
        self.subnet_id = subnet_id
        self.port_id = port_id
        self.new_insert = False

    def _get_dhcp_options_row(self):
        for row in self.api._tables['DHCP_Options'].rows.values():
            external_ids = getattr(row, 'external_ids', {})
            port_id = external_ids.get('port_id')
            if self.subnet_id == external_ids.get('subnet_id'):
                if self.port_id == port_id:
                    return row

    def run_idl(self, txn):
        row = None
        if self.may_exists:
            row = self._get_dhcp_options_row()

        if not row:
            row = txn.insert(self.api._tables['DHCP_Options'])
            self.new_insert = True
        for col, val in self.columns.items():
            setattr(row, col, val)
        self.result = row.uuid

    def post_commit(self, txn):
        # Update the result with inserted uuid for new inserted row, or the
        # uuid get in run_idl should be real uuid already.
        if self.new_insert:
            self.result = txn.get_insert_uuid(self.result)


class DelDHCPOptionsCommand(command.BaseCommand):
    def __init__(self, api, row_uuid, if_exists=True):
        super(DelDHCPOptionsCommand, self).__init__(api)
        self.if_exists = if_exists
        self.row_uuid = row_uuid

    def run_idl(self, txn):
        if self.row_uuid not in self.api._tables['DHCP_Options'].rows:
            if self.if_exists:
                return
            msg = _("DHCP Options row %s does not exist") % self.row_uuid
            raise RuntimeError(msg)

        self.api._tables['DHCP_Options'].rows[self.row_uuid].delete()


class AddNATRuleInLRouterCommand(command.BaseCommand):
    # TODO(chandrav): Add unit tests, bug #1638715.
    def __init__(self, api, lrouter, **columns):
        super(AddNATRuleInLRouterCommand, self).__init__(api)
        self.lrouter = lrouter
        self.columns = columns

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        row = txn.insert(self.api._tables['NAT'])
        for col, val in self.columns.items():
            setattr(row, col, val)
        # TODO(chandrav): convert this to ovs transaction mutate
        lrouter.verify('nat')
        nat = getattr(lrouter, 'nat', [])
        nat.append(row.uuid)
        setattr(lrouter, 'nat', nat)


class DeleteNATRuleInLRouterCommand(command.BaseCommand):
    # TODO(chandrav): Add unit tests, bug #1638715.
    def __init__(self, api, lrouter, type, logical_ip, external_ip,
                 if_exists):
        super(DeleteNATRuleInLRouterCommand, self).__init__(api)
        self.lrouter = lrouter
        self.type = type
        self.logical_ip = logical_ip
        self.external_ip = external_ip
        self.if_exists = if_exists

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            if self.if_exists:
                return
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        lrouter.verify('nat')
        # TODO(chandrav): convert this to ovs transaction mutate
        nats = getattr(lrouter, 'nat', [])
        for nat in nats:
            type = getattr(nat, 'type', '')
            external_ip = getattr(nat, 'external_ip', '')
            logical_ip = getattr(nat, 'logical_ip', '')
            if self.type == type and \
               self.external_ip == external_ip and \
               self.logical_ip == logical_ip:
                nats.remove(nat)
                nat.delete()
                break
        setattr(lrouter, 'nat', nats)


class SetNATRuleInLRouterCommand(command.BaseCommand):
    def __init__(self, api, lrouter, nat_rule_uuid, **columns):
        super(SetNATRuleInLRouterCommand, self).__init__(api)
        self.lrouter = lrouter
        self.nat_rule_uuid = nat_rule_uuid
        self.columns = columns

    def run_idl(self, txn):
        try:
            lrouter = idlutils.row_by_value(self.api.idl, 'Logical_Router',
                                            'name', self.lrouter)
        except idlutils.RowNotFound:
            msg = _("Logical Router %s does not exist") % self.lrouter
            raise RuntimeError(msg)

        lrouter.verify('nat')
        nat_rules = getattr(lrouter, 'nat', [])
        for nat_rule in nat_rules:
            if nat_rule.uuid == self.nat_rule_uuid:
                for col, val in self.columns.items():
                    setattr(nat_rule, col, val)
                break


class AddNatIpToLRPortPeerOptionsCommand(command.BaseCommand):
    # TODO(chandrav): Add unit tests, bug #1638715.
    def __init__(self, api, lport, nat_ip):
        super(AddNatIpToLRPortPeerOptionsCommand, self).__init__(api)
        self.lport = lport
        self.nat_ip = nat_ip

    def run_idl(self, txn):
        try:
            lport = idlutils.row_by_value(self.api.idl, 'Logical_Switch_Port',
                                          'name', self.lport)
        except idlutils.RowNotFound:
            msg = _("Logical Switch Port %s does not exist") % self.lport
            raise RuntimeError(msg)

        lport.verify('addresses')
        addresses = getattr(lport, 'addresses', [])
        lport.verify('options')
        options = getattr(lport, 'options', {})

        nat_ip_list = options.get('nat-addresses', '').split()
        if not nat_ip_list:
            nat_ips = addresses[0].split()[0] + ' ' + self.nat_ip
        elif self.nat_ip not in nat_ip_list:
            nat_ip_list.append(self.nat_ip)
            nat_ips = ' '.join(nat_ip_list)
        else:
            return
        options['nat-addresses'] = nat_ips
        lport.options = options


class DeleteNatIpFromLRPortPeerOptionsCommand(command.BaseCommand):
    # TODO(chandrav): Add unit tests, bug #1638715.
    def __init__(self, api, lport, nat_ip):
        super(DeleteNatIpFromLRPortPeerOptionsCommand, self).__init__(api)
        self.lport = lport
        self.nat_ip = nat_ip

    def run_idl(self, txn):
        try:
            lport = idlutils.row_by_value(self.api.idl, 'Logical_Switch_Port',
                                          'name', self.lport)

        except idlutils.RowNotFound:
            msg = _("Logical Switch Port %s does not exist") % self.port
            raise RuntimeError(msg)

        lport.verify('options')
        options = getattr(lport, 'options', {})
        nat_ip_list = options.get('nat-addresses', '').split()
        if self.nat_ip not in nat_ip_list:
            return
        nat_ip_list.remove(self.nat_ip)
        if len(nat_ip_list) is 1:
            nat_ips = ''
        else:
            nat_ips = ' '.join(nat_ip_list)
        if not nat_ips:
            del options['nat-addresses']
        else:
            options['nat-addresses'] = nat_ips
        lport.options = options
