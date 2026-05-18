# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import utils


def pre_init_hook(env):
    """Arregla FK constraints antes de que el ORM intente modificar registros."""
    env.cr.execute("""
        ALTER TABLE hr_experience
        DROP CONSTRAINT IF EXISTS hr_experience_employee_id_fkey;
        ALTER TABLE hr_experience
        ADD CONSTRAINT hr_experience_employee_id_fkey
        FOREIGN KEY (employee_id) REFERENCES hr_employee(id) ON DELETE CASCADE;
    """)
