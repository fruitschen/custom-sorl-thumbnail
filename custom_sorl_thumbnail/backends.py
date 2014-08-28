import os, re
try:
    import ImageEnhance
except:
    from PIL import ImageEnhance
from PIL import Image, ImageFilter, ImageChops, ImageOps
from sorl.thumbnail.base import ThumbnailBackend
from django.template.defaultfilters import slugify
from django.conf import settings
from sorl.thumbnail import default
from sorl.thumbnail.base import ThumbnailBackend
from sorl.thumbnail.helpers import tokey, serialize
from sorl.thumbnail.images import ImageFile

class SEOThumbnailBackend(ThumbnailBackend):
    """
    Custom backend for SEO-friendly thumbnail file names/urls.
    based on http://blog.yawd.eu/2012/seo-friendly-image-names-sorl-thumbnail-and-django/
    """
    def _get_thumbnail_filename(self, source, geometry_string, options):###customization
        """
        Computes the destination filename.
        """
        try:
            root_path = source.storage.path('')
        except: 
            #some storage backends do not support path() 
            root_path = ''
        split_path = re.sub(r'^%s%s?' % (root_path, os.sep), '', source.name).split(os.sep)
        split_path.insert(-1, geometry_string)

        #make some subdirs to avoid putting too many files in a single dir. 
        key = tokey(source.key, geometry_string, serialize(options))
        split_path.insert(-1, key[:2])
        split_path.insert(-1, key[2:4])

        #attempt to slugify the filename to make it SEO-friendly
        split_name = split_path[-1].split('.')
        try:
            split_path[-1] = '%s.%s' % (slugify('.'.join(split_name[:-1])), split_name[-1])
        except:
            #on fail keep the original filename
            pass
        
        path = os.sep.join(split_path)
        
        #if the path already starts with THUMBNAIL_PREFIX do not concatenate the PREFIX
        #this way we avoid ending up with a url like /images/images/120x120/my.png
        if not path.startswith(settings.THUMBNAIL_PREFIX):
            return '%s%s' % (settings.THUMBNAIL_PREFIX, path) 
        
        return path


class SafeSEOThumbnailBackend(SEOThumbnailBackend):
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
            size = default.engine.get_image_size(source_image)
            if options.get('autocrop', None):
                source_image = autocrop(source_image, geometry_string, options)
            # We might as well set the size since we have the image in memory
            size = default.engine.get_image_size(source_image)
            source.set_size(size)
            ### customization: race condition, do not raise an OSError when the dir exists.
            # see sorl.thumbnail.images.ImageFile.write, it's not safe to simply throw
            # /sub/dir/name.jpg to django.core.files.storage.FileSystemStorage._save 
            full_path = thumbnail.storage.path(name)
            directory = os.path.dirname(full_path)
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                except OSError:
                    pass
            ### end of customization
            self._create_thumbnail(source_image, geometry_string, options,
                                   thumbnail)
        # If the thumbnail exists we don't create it, the other option is
        # to delete and write but this could lead to race conditions so I
        # will just leave that out for now.
        default.kvstore.get_or_set(source)
        default.kvstore.set(thumbnail, source)
        return thumbnail


def autocrop(im, requested_size, opts):
    if 'autocrop' in opts:
        image = ImageEnhance.Brightness(im).enhance(1.12)
        inverted_image = ImageOps.invert(image)
        bbox = inverted_image.getbbox()
        if bbox:
            im = im.crop(bbox)
        '''
        bw = im.convert("1")
        bw = bw.filter(ImageFilter.MedianFilter)
        # white bg
        bg = Image.new("1", im.size, 255)
        diff = ImageChops.difference(bw, bg)
        bbox = diff.getbbox()
        if bbox:
            im = im.crop(bbox)
        '''
    return im

