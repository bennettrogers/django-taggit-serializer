# -*- coding: utf-8 -*-
import json

# Third party
import six
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class TagList(list):
    def __init__(self, *args, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)
        list.__init__(self, *args, **kwargs)
        self.pretty_print = pretty_print

    def __add__(self, rhs):
        return TagList(list.__add__(self, rhs))

    def __getitem__(self, item):
        result = list.__getitem__(self, item)
        try:
            return TagList(result)
        except TypeError:
            return result

    def __str__(self):
        if self.pretty_print:
            return json.dumps(self, sort_keys=True, indent=4, separators=(",", ": "))
        else:
            return json.dumps(self)


class TagListSerializerField(serializers.Field):
    #  child = serializers.CharField()
    default_error_messages = {
        "not_a_list": _('Expected a list of items but got type "{input_type}".'),
        "invalid_json": _(
            "Invalid json list. A tag list submitted in string"
            " form must be valid json."
        ),
        "invalid_type": _("All list items must be of type str or dict."),
    }
    order_by = None

    def __init__(self, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)

        style = kwargs.pop("style", {})
        kwargs["style"] = {"base_template": "textarea.html"}
        kwargs["style"].update(style)

        super(TagListSerializerField, self).__init__(**kwargs)

        self.pretty_print = pretty_print

    def to_internal_value(self, value):
        # If value is None or a string, parse it into a json dict
        if isinstance(value, six.string_types):
            if not value:
                value = "[]"
            try:
                value = json.loads(value)
            except ValueError:
                self.fail("invalid_json")

        # If value is not a list, make it one
        if not isinstance(value, list):
            value = [value]

        # Items in the list must either be strings or dicts
        for s in value:
            if not isinstance(s, six.string_types) and not isinstance(s, dict):
                self.fail("invalid_type")

            #  self.child.run_validation(s)

        return value

    def to_representation(self, value):
        # "value" here is assumed to be an instance of _TaggableManager, which is why it has an ".all()" method
        if not isinstance(value, TagList):
            if not isinstance(value, list):
                if self.order_by:
                    tags = value.all().order_by(*self.order_by)
                else:
                    tags = value.all()
                value = [tag.name for tag in tags]
            value = TagList(value, pretty_print=self.pretty_print)

        return value


class TaggitSerializer(serializers.Serializer):
    def create(self, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).create(validated_data)

        return self._save_tags(tag_object, to_be_tagged)

    def update(self, instance, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).update(instance, validated_data)

        return self._save_tags(tag_object, to_be_tagged)

    def _save_tags(self, tag_object, tags):
        for key in tags.keys():
            tag_values = tags.get(key)

            taggable_manager = getattr(tag_object, key)

            # New tags can either be strings or tag model instances
            new_tags = []
            tag_dict_ids = []
            for tag in tag_values:
                if isinstance(tag, six.string_types):
                    new_tags.append(tag)
                elif isinstance(tag, dict):
                    try:
                        tag_dict_ids.append(tag["id"])
                    except KeyError:
                        raise serializers.ValidationError(
                            "Tag instance dicts must have an id."
                        )
                else:
                    raise serializers.ValidationError(
                        "All tags must either be strings or dicts"
                    )

            # Get the tag objects
            # Use the appropriate tag model. This method is used in the taggit source:
            # https://github.com/alex/django-taggit/blob/0.23.0/taggit/managers.py#L152
            TagModel = taggable_manager.through.tag_model()
            tag_dict_objs = TagModel.objects.filter(id__in=tag_dict_ids)
            new_tags = new_tags + list(tag_dict_objs)

            # TaggableManager.set expects args to be strings or Tag Model instances
            taggable_manager.set(*new_tags)

        return tag_object

    def _pop_tags(self, validated_data):
        to_be_tagged = {}

        for key in self.fields.keys():
            field = self.fields[key]
            if isinstance(field, TagListSerializerField):
                if key in validated_data:
                    to_be_tagged[key] = validated_data.pop(key)

        return (to_be_tagged, validated_data)
