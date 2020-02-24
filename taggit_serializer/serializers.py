# -*- coding: utf-8 -*-
import json

# Third party
import six
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


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
        serialize_slugs = kwargs.pop("slugs", False)

        style = kwargs.pop("style", {})
        kwargs["style"] = {"base_template": "textarea.html"}
        kwargs["style"].update(style)

        TagSerializer = kwargs.pop("serializer", None)

        super(TagListSerializerField, self).__init__(**kwargs)

        self.pretty_print = pretty_print
        self.serialize_slugs = serialize_slugs
        self.TagSerializer = TagSerializer

    def to_internal_value(self, value):
        # Incoming value can be an empty string, a single string, a list of strings, a dict, or a list of dicts
        # In either case, convert it to a list first

        if isinstance(value, six.string_types):
            # If empty string, set value to empty list string
            if not value:
                value = "[]"

            # If the incoming value is a stringified dict or stringified list of dicts,
            # convert it to a dict or list of dicts.
            # Do not fail in case the incoming value is just a single string.
            # Note: this means that we will not detect the case where the string was supposed to
            # be a stringified dict but it is malformed. There isn't a way to determine whether a string
            # is a simple string (e.g. a slug) or a malformed JSON string.
            try:
                value = json.loads(value)
            except ValueError:
                pass

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
        if not isinstance(value, list):
            if self.order_by:
                tags = value.all().order_by(*self.order_by)
            else:
                tags = value.all()
            # If a serializer was specified, use it to return the representation. Otherwise just return the tag name
            if self.TagSerializer:
                value = [self.TagSerializer(tag).data for tag in tags]
            else:
                value = [tag.slug if self.serialize_slugs else tag.name for tag in tags]

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
