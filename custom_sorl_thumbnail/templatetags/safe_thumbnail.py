import os.path
import logging
import re
from django.template import Library
from sorl.thumbnail.conf import settings
from sorl.thumbnail.images import DummyImageFile
from sorl.thumbnail import default
from sorl.thumbnail.templatetags.thumbnail import ThumbnailNode
from sorl.thumbnail.base import ThumbnailBackend
from sorl.thumbnail.images import ImageFile
from sorl.thumbnail import default


register = Library()
kw_pat = re.compile(r'^(?P<key>[\w]+)=(?P<value>.+)$')
logger = logging.getLogger('sorl.thumbnail')


class CustomThumbnailBackend(ThumbnailBackend):

    def get_thumbnail(self, file_, geometry_string, **options):
        """
        Returns thumbnail as an ImageFile instance for file with geometry and
        options given. First it will try to get it from the key value store,
        secondly it will create it.
        """
        source = ImageFile(file_)
        for key, value in self.default_options.iteritems():
            options.setdefault(key, value)
        options['mtime'] = os.path.getmtime(source.storage.path(source))###customization
        name = self._get_thumbnail_filename(source, geometry_string, options)
        thumbnail = ImageFile(name, default.storage)
        cached = default.kvstore.get(thumbnail)
        if cached and cached.exists():###customization
            return cached
        if not thumbnail.exists():
            # We have to check exists() because the Storage backend does not
            # overwrite in some implementations.
            source_image = default.engine.get_image(source)
            # We might as well set the size since we have the image in memory
            size = default.engine.get_image_size(source_image)
            source.set_size(size)
            self._create_thumbnail(source_image, geometry_string, options,
                                   thumbnail)
        # If the thumbnail exists we don't create it, the other option is
        # to delete and write but this could lead to race conditions so I
        # will just leave that out for now.
        default.kvstore.get_or_set(source)
        default.kvstore.set(thumbnail, source)
        return thumbnail
        
custom_backend = CustomThumbnailBackend()


#@register.tag('thumbnail')
class SafeThumbnailNode(ThumbnailNode):
    child_nodelists = ('nodelist_file', 'nodelist_empty')
    error_msg = ('Syntax error. Expected: ``thumbnail source geometry '
                 '[key1=val1 key2=val2...] as var``')

    def _render(self, context):
        file_ = self.file_.resolve(context)
        geometry = self.geometry.resolve(context)
        options = {}
        for key, expr in self.options:
            noresolve = {u'True': True, u'False': False, u'None': None}
            value = noresolve.get(unicode(expr), expr.resolve(context))
            if key == 'options':
                options.update(value)
            else:
                options[key] = value
        if settings.THUMBNAIL_DUMMY:
            thumbnail = DummyImageFile(geometry)
        elif file_:
            thumbnail = custom_backend.get_thumbnail(###customization
                file_, geometry, **options
                )
        else:
            return self.nodelist_empty.render(context)
        context.push()
        context[self.as_var] = thumbnail
        output = self.nodelist_file.render(context)
        context.pop()
        return output


@register.tag
def thumbnail(parser, token):
    return SafeThumbnailNode(parser, token)
