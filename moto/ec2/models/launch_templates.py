from collections import OrderedDict
from ..utils import generic_filter, random_launch_template_id, utc_date_and_time
from ..exceptions import (
    InvalidLaunchTemplateNameAlreadyExistsError,
    InvalidLaunchTemplateNameNotFoundError,
)
from moto.core import CloudFormationModel

class LaunchTemplateVersion(object):
    def __init__(self, template, number, data, description):
        self.template = template
        self.number = number
        self.data = data
        self.description = description
        self.create_time = utc_date_and_time()

    @property
    def image_id(self):
        return self.data.get("ImageId", "")

    @property
    def instance_type(self):
        return self.data.get("InstanceType", "")

    @property
    def security_groups(self):
        return self.data.get("SecurityGroups", [])

    @property
    def user_data(self):
        return self.data.get("UserData", "")


class LaunchTemplateBackend:
    def __init__(self):
        self.launch_template_name_to_ids = {}
        self.launch_templates = OrderedDict()
        self.launch_template_insert_order = []

    def create_launch_template(self, name, template_data, tag_specifications, description=None):
        if name in self.launch_template_name_to_ids:
            raise InvalidLaunchTemplateNameAlreadyExistsError()
        template = FakeLaunchTemplate(name, template_data, tag_specifications, description)
        self.launch_templates[template.id] = template
        self.launch_template_name_to_ids[template.launch_template_name] = template.id
        self.launch_template_insert_order.append(template.id)
        return template

    def get_launch_template(self, template_id):
        return self.launch_templates[template_id]

    def get_launch_template_by_name(self, name):
        return self.get_launch_template(self.launch_template_name_to_ids[name])

    def delete_launch_template(self, name, tid):
        if name:
            tid = self.launch_template_name_to_ids[name]
        return self.launch_templates.pop(tid)

    def describe_launch_templates(
        self, template_names=None, template_ids=None, filters=None
    ):
        if template_names and not template_ids:
            template_ids = []
            for name in template_names:
                if name not in self.launch_template_name_to_ids:
                    raise InvalidLaunchTemplateNameNotFoundError()
                template_ids.append(self.launch_template_name_to_ids[name])

        if template_ids:
            templates = [
                self.launch_templates[tid]
                for tid in template_ids
                if tid in self.launch_templates
            ]
        else:
            templates = list(self.launch_templates.values())

        return generic_filter(filters, templates)


class FakeLaunchTemplate(CloudFormationModel):
    def __init__(self, launch_template_name, launch_template_data, tag_specifications, description):
        self.launch_template_data = launch_template_data
        self.launch_template_name = launch_template_name
        self.tag_specifications = tag_specifications
        self.description = description
        self.id = random_launch_template_id()
        self.create_time = utc_date_and_time()

        self.versions = []
        self.create_version(launch_template_data, description)
        self.default_version_number = 1

    @property
    def physical_resource_id(self):
        return self.arn

    @staticmethod
    def cloudformation_type():
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-launchtemplate.html
        return "AWS::EC2::LaunchTemplate"

    def create_version(self, data, description):
        num = len(self.versions) + 1
        version = LaunchTemplateVersion(self, num, data, description)
        self.versions.append(version)
        return version

    def is_default(self, version):
        return self.default_version == version.number

    def get_version(self, num):
        if str(num).lower() == "$latest":
            return self.versions[-1]
        if str(num).lower() == "$default":
            return self.default_version()
        return self.versions[int(num) - 1]

    @property
    def latest_version_number(self):
        return self.latest_version().number

    def get_filter_value(self, filter_name):
        if filter_name == "launch-template-name":
            return self.name
        else:
            return super().get_filter_value(filter_name, "DescribeLaunchTemplates")

    def default_version(self):
        return self.versions[self.default_version_number - 1]

    def latest_version(self):
        return self.versions[-1]

    @classmethod
    def create_from_cloudformation_json(
        cls, resource_name, cloudformation_json, account_id, region_name, **kwargs
    ):
        from ..models import ec2_backends

        properties = cloudformation_json["Properties"]

        launch_template_data = properties.get("LaunchTemplateData")
        launch_template_name = properties.get("LaunchTemplateName")
        tag_specifications = properties.get("TagSpecifications")

        ec2_backend = ec2_backends[account_id][region_name]

        launch_template = ec2_backend.create_launch_template(
            launch_template_name, launch_template_data, tag_specifications
        )
        return launch_template
