"""Helper form yg dipake bareng semua route: ambil isi form, tempel error dari service, tampilin error."""
from flask import flash

def read_form_data(form, field_name_list):
    """Isi form jadi dict, cuma field yg disebut."""
    return {field_name: form[field_name].data for field_name in field_name_list}

def attach_form_error_list(form, error_list):
    """Error dari service ditempel ke field form-nya. Return error yg ga punya field di form (biar pemanggil yg nentuin)."""
    leftover_list = []
    for error_dict in error_list:
        field_name = error_dict.get("field")
        if field_name and field_name in form:
            form[field_name].errors.append(error_dict["message"])
        else:
            leftover_list.append(error_dict)
    return leftover_list

def flash_error_list(error_list):
    """Tampilin error sebagai flash merah."""
    for error_dict in error_list:
        flash(error_dict["message"], "danger")
