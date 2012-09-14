import decimal

from django.conf import settings

from sorl.thumbnail.fields import ImageField as SorlImageField

__all__ = ('ImageField')


def resize_image(file):
    from PIL import Image
    max_width = decimal.Decimal(getattr(settings, 'MAXIMUM_IMAGE_WIDTH', 1280))
    max_height = decimal.Decimal(getattr(settings, 'MAXIMUM_IMAGE_HEIGHT', 1024))

    try:
        im = Image.open(file.path)
    except IOError:
        im = None
    if im:
        current_width, current_height = im.size
        current_width, current_height = decimal.Decimal(current_width), decimal.Decimal(current_height)
        if current_width > max_width or current_height > max_height:
            if current_width > max_width and current_height > max_height:
                ratios = (max_width/current_width, max_height/current_height)
                ratio = min(ratios)
            elif current_width > max_width:
                ratio = max_width/current_width
            elif current_height > max_height:
                ratio = max_height/current_height
            new_width = int(current_width * ratio)
            new_height = int(current_height * ratio)
            new_size = (new_width, new_height)
            im.thumbnail(new_size, Image.ANTIALIAS)
            im.save(file.path)


class ImageField(SorlImageField):

    def pre_save(self, model_instance, add):
        "Returns field's value just before saving."
        file = super(ImageField, self).pre_save(model_instance, add)
        resize_image(file)
        print self.south_field_triple()
        return file

