# vCenter client module for SDDC Import/Export for VMware Cloud on AWS
################################################################################
### Copyright 2020-2021 VMware, Inc.
### SPDX-License-Identifier: BSD-2-Clause
################################################################################
import json
import ssl

import com.vmware.vcenter_client
import pyVim.connect
from pyVmomi import vim
import pyVmomi.VmomiSupport
import requests
from vmware.vapi.vsphere.client import create_vsphere_client

# Example
# vc = vCenter('vcsa-01a.corp.local', 'administrator@vsphere.local', 'VMware1!', ssl_verification=False)
# dc = vc.get_datacenter('RegionA01-ATL')


class Datacenter:
    def __init__(self, name, service_instance, vsphere_client):
        self._name = name
        self._service_instance = service_instance
        self._vsphere_client = vsphere_client

        self._content = self._service_instance.RetrieveContent()
        self._datacenter_obj = self._get_datacenter_obj()

    @property
    def id(self):
        return self._datacenter_obj._moId

    @property
    def name(self):
        return self._name

    def _get_datacenter_obj(self) -> vim.Datacenter:
        """
        Returns the identifier of a datacenter
        Note: The method assumes only one datacenter with the mentioned name.
        """
        container = self._content.viewManager.CreateContainerView(
            container=self._content.rootFolder,
            type=[vim.Datacenter],
            recursive=False
        )

        for managed_object in container.view:
            if managed_object.name == self._name:
                return managed_object
        else:
            raise RuntimeError(f'Could not find datacenter {self._name}')

    def _get_folder_by_name(self, folder_name: str, parent_folder: vim.Folder = None) -> vim.Folder:
        if not parent_folder:
            parent_folder = self._datacenter_obj.vmFolder

        for child_item in parent_folder.childEntity:
            if type(child_item) == vim.Folder and child_item.name == folder_name:
                return child_item
        else:
            raise RuntimeError(f'Could not find folder {folder_name}')

    def _get_folder_by_path(self, folder_path: str) -> vim.Folder:
        # Ignoring the first item from the split as it's the empty string before the first /
        folder_names = folder_path.split('/')[1:]

        # If "root" folder specified then folder_names will be empty.
        if folder_names:
            root_folder_name = folder_names.pop(0)
            folder = self._get_folder_by_name(root_folder_name)
        else:
            folder = self._datacenter_obj.vmFolder

        for folder_name in folder_names:
            folder = self._get_folder_by_name(folder_name, parent_folder=folder)

        return folder

    def _get_folder_children(self, folder: vim.Folder, parent_path: str = '') -> list:
        parent_folder = self._content.viewManager.CreateContainerView(
            container=folder,
            type=[vim.Folder],
            recursive=False
        )

        child_paths = []
        for folder in parent_folder.view:
            path = f'{parent_path}/{folder.name}'
            child_paths.append(path)
            child_paths.extend(self._get_folder_children(folder, parent_path=path))

        return child_paths

    def _create_folder_by_path(self, folder_path: str) -> vim.Folder:
        parent_folder_path, folder_name = folder_path.rsplit('/', 1)
        parent_folder = self._get_folder_by_path(parent_folder_path)
        try:
            folder = parent_folder.CreateFolder(folder_name)
            print(f'Folder {folder_path} created.')
            return folder
        except vim.fault.DuplicateName:
            print(f'Folder {folder_path} already exists, skipping.')


    def export_folder_paths(self, export_file_path: str) -> None:
        vm_folder = self._datacenter_obj.vmFolder
        folder_paths = self._get_folder_children(vm_folder)
        with open(export_file_path, 'w') as paths_file:
            json.dump(folder_paths, paths_file)

    def import_folder_paths(self, import_file_path: str, test_mode: bool = False) -> None:
        with open(import_file_path) as paths_file:
            folder_paths = json.load(paths_file)

        for folder_path in folder_paths:
            if test_mode:
                print(f'TEST MODE: would have created {folder_path}')
            else:
                self._create_folder_by_path(folder_path)

    def _get_vm_by_name(self, vm_name: str, parent_folder: vim.Folder = None) -> vim.VirtualMachine:
        if not parent_folder:
            parent_folder = self._datacenter_obj.vmFolder

        for child_item in parent_folder.childEntity:
            if type(child_item) == vim.VirtualMachine and child_item.name == vm_name:
                return child_item
        else:
            raise RuntimeError(f'Could not find VM {vm_name}')

    def _get_vm_by_path(self, vm_path: str) -> vim.VirtualMachine:
        folder_path, vm_name = vm_path.rsplit('/', 1)
        folder = self._get_folder_by_path(folder_path)
        vm = self._get_vm_by_name(vm_name, parent_folder=folder)
        return vm

    def _create_tag_category(self, name, description, cardinality, associable_types):
        create_spec = self._vsphere_client.tagging.Category.CreateSpec()
        create_spec.name = name
        create_spec.description = description
        create_spec.cardinality = cardinality
        create_spec.associable_types = set(associable_types)
        return self._vsphere_client.tagging.Category.create(create_spec)

    def _create_tag(self, name, description, category_id):
        create_spec = self._vsphere_client.tagging.Tag.CreateSpec()
        create_spec.name = name
        create_spec.description = description
        create_spec.category_id = category_id
        return self._vsphere_client.tagging.Tag.create(create_spec)

    def _get_tag_categories(self):
        categories = set()
        for id in self._vsphere_client.tagging.Category.list():
            category = self._vsphere_client.tagging.Category.get(id)
            categories.add (category.name)
        return categories

    def _get_tags(self):
        tags = set()
        for id in self._vsphere_client.tagging.Tag.list():
            tag = self._vsphere_client.tagging.Tag.get(id)
            tags.add (tag.name)
        return tags

    def export_tag_categories(self, export_file_path: str) -> None:
        categories = []
        for id in self._vsphere_client.tagging.Category.list():
            category = self._vsphere_client.tagging.Category.get(id)
            new_category = {}
            new_category['name'] = category.name
            new_category['description'] = category.description
            new_category['cardinality'] = category.cardinality
            new_category['associable_types'] = list(category.associable_types)
            categories.append(new_category)

        with open(export_file_path, 'w') as paths_file:
            json.dump(categories, paths_file)

    def export_tags(self, export_file_path: str) -> None:
        categories = {}
        tags = []
        for id in self._vsphere_client.tagging.Category.list():
            category = self._vsphere_client.tagging.Category.get(id)
            categories[category.id] = category.name
        for id in self._vsphere_client.tagging.Tag.list():
            tag = self._vsphere_client.tagging.Tag.get(id)
            new_tag = {}
            new_tag['name'] = tag.name
            new_tag['category'] = categories[tag.category_id]
            new_tag['description'] = tag.description
            tags.append(new_tag)

        with open(export_file_path, 'w') as paths_file:
            json.dump(tags, paths_file)

    def import_tag_categories(self, import_file_path: str, test_mode: bool = False) -> None:
        with open(import_file_path) as paths_file:
            categories = json.load(paths_file)

        existing_categories = self._get_tag_categories()

        for category in categories:
            if test_mode:
                print(f'TEST MODE: would have created category {category}')
            else:
                if category['name'] not in existing_categories:
                    self._create_tag_category(category['name'], category['description'], category['cardinality'], category['associable_types'] )

    def import_tags(self, import_file_path: str, test_mode: bool = False) -> None:
        with open(import_file_path) as paths_file:
            tags = json.load(paths_file)

        categories = {}
        for id in self._vsphere_client.tagging.Category.list():
            category = self._vsphere_client.tagging.Category.get(id)
            categories[category.name] = category.id

        existing_tags = self._get_tags()

        for tag in tags:
            if test_mode:
                print(f'TEST MODE: would have created tag {tag}')
            else:
                if tag['name'] not in existing_tags:
                    self._create_tag(tag['name'], tag['description'],categories[tag['category']])

class vCenter:
    def __init__(self, address, username, password, ssl_verification=False):
        self._address = address
        self._username = username
        self._password = password
        self._service_instance = None # SOAP
        self._ssl_verification = ssl_verification
        self._vsphere_client = None  # REST
        self._create_service_instance()
        self._create_vsphere_client()

    def _create_service_instance(self):
        connect_args = {
            'host': self._address,
            'user': self._username,
            'pwd': self._password
        }

        if not self._ssl_verification:
            # Todo: Create context without using private function?
            connect_args['sslContext'] = ssl._create_unverified_context()

        self._service_instance = pyVim.connect.SmartConnect(**connect_args)

    def _create_vsphere_client(self):
        connect_args = {
            'server': self._address,
            'username': self._username,
            'password': self._password
        }

        if not self._ssl_verification:
            session = requests.session()
            session.verify = False
            requests.packages.urllib3.disable_warnings()
            connect_args['session'] = session
        
        self._vsphere_client = create_vsphere_client(**connect_args)

    def get_datacenter(self, datacenter_name: str) -> Datacenter:
        return Datacenter(datacenter_name, self._service_instance, self._vsphere_client)
