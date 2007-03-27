/*
 * Copyright: 2006-2007 Brian Harring <ferringb@gmail.com>
 * License: GPL2
 *
 * C version of some of snakeoil (for extra speed).
 */

/* This does not really do anything since we do not use the "#"
 * specifier in a PyArg_Parse or similar call, but hey, not using it
 * means we are Py_ssize_t-clean too!
 */

#define PY_SSIZE_T_CLEAN
#include "snakeoil/common.h"
#include <ceval.h>

static PyObject *snakeoil_equality_attr = NULL;

typedef struct {
    PyObject_HEAD
    PyObject *redirect_target;
} snakeoil_GetAttrProxy;

static void
snakeoil_GetAttrProxy_dealloc(snakeoil_GetAttrProxy *self)
{
    Py_CLEAR(self->redirect_target);
    self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_GetAttrProxy_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    snakeoil_GetAttrProxy *self;
    PyObject *alias_attr;

    if(!PyArg_ParseTuple(args, "S:__new__", &alias_attr))
        return NULL;
    self = (snakeoil_GetAttrProxy *)type->tp_alloc(type, 0);

    if (self) {
        self->redirect_target = alias_attr;
        Py_INCREF(alias_attr);
    }
    return (PyObject *)self;
}

static PyObject *
snakeoil_GetAttrProxy_call(snakeoil_GetAttrProxy *self, PyObject *args,
    PyObject *kwds)
{
    PyObject *attr, *real_obj, *tmp = NULL;

    if(PyArg_ParseTuple(args, "OS:__call__", &real_obj, &attr)) {
        if(Py_EnterRecursiveCall(" in GetAttrProxy.__call__ "))
            return NULL;
        real_obj = PyObject_GenericGetAttr(real_obj, self->redirect_target);
        if(real_obj) {
            tmp = PyObject_GetAttr(real_obj, attr);
            Py_DECREF(real_obj);
        }
        Py_LeaveRecursiveCall();
    }
    return (PyObject *)tmp;
}


static PyTypeObject snakeoil_GetAttrProxyType = {
    PyObject_HEAD_INIT(NULL)
    0,                                               /* ob_size */
    "snakeoil._klass.GetAttrProxy",                  /* tp_name */
    sizeof(snakeoil_GetAttrProxy),                    /* tp_basicsize */
    0,                                               /* tp_itemsize */
    (destructor)snakeoil_GetAttrProxy_dealloc,        /* tp_dealloc */
    0,                                               /* tp_print */
    0,                                               /* tp_getattr */
    0,                                               /* tp_setattr */
    0,                                               /* tp_compare */
    0,                                               /* tp_repr */
    0,                                               /* tp_as_number */
    0,                                               /* tp_as_sequence */
    0,                                               /* tp_as_mapping */
    0,                                               /* tp_hash  */
    (ternaryfunc)snakeoil_GetAttrProxy_call,          /* tp_call */
    (reprfunc)0,                                     /* tp_str */
    0,                                               /* tp_getattro */
    0,                                               /* tp_setattro */
    0,                                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,         /* tp_flags */
    "GetAttrProxy object; used mainly for native __getattr__ speed",
                                                     /* tp_doc */
    0,                                               /* tp_traverse */
    0,                                               /* tp_clear */
    0,                                               /* tp_richcompare */
    0,                                               /* tp_weaklistoffset */
    0,                                               /* tp_iter */
    0,                                               /* tp_iternext */
    0,                                               /* tp_methods */
    0,                                               /* tp_members */
    0,                                               /* tp_getset */
    0,                                               /* tp_base */
    0,                                               /* tp_dict */
    0,                                               /* tp_descr_get */
    0,                                               /* tp_descr_set */
    0,                                               /* tp_dictoffset */
    0,                                               /* tp_init */
    0,                                               /* tp_alloc */
    snakeoil_GetAttrProxy_new,                        /* tp_new */

};

static PyObject *
snakeoil_mapping_get(PyObject *self, PyObject *args)
{
    PyObject *key, *default_val = Py_None;
    if(!self) {
        PyErr_SetString(PyExc_TypeError,
            "need to be called with a mapping as the first arg");
        return NULL;
    }
    if(!PyArg_UnpackTuple(args, "get", 1, 2, &key, &default_val))
        return NULL;

    PyObject *ret = PyObject_GetItem(self, key);
    if(ret) {
        return ret;
    } else if (!PyErr_ExceptionMatches(PyExc_KeyError)) {
        return NULL;
    }

    PyErr_Clear();
    Py_INCREF(default_val);
    return default_val;
}

static inline PyObject *
internal_generic_equality(PyObject *inst1, PyObject *inst2,
    int desired)
{
    if(inst1 == inst2) {
        PyObject *res = desired == Py_EQ ? Py_True : Py_False;
        Py_INCREF(res);
        return res;
    }

    PyObject *attrs = PyObject_GetAttr(inst1, snakeoil_equality_attr);
    if(!attrs)
        return NULL;
    if(!PyTuple_CheckExact(attrs)) {
        PyErr_SetString(PyExc_TypeError,
            "__attr_comparison__ must be a tuple");
        return NULL;
    }

    Py_ssize_t idx = 0;
    PyObject *attr1, *attr2;
    // if Py_EQ, break on not equal, else on equal
    for(; idx < PyTuple_GET_SIZE(attrs); idx++) {

        attr1 = PyObject_GetAttr(inst1, PyTuple_GET_ITEM(attrs, idx));
        if(!attr1) {
            if(!PyErr_ExceptionMatches(PyExc_AttributeError))
                return NULL;
             PyErr_Clear();
        }

        attr2 = PyObject_GetAttr(inst2, PyTuple_GET_ITEM(attrs, idx));
        if(!attr2) {
            if(!PyErr_ExceptionMatches(PyExc_AttributeError)) {
                Py_XDECREF(attr1);
                return NULL;
            }
            PyErr_Clear();
        }
        if(!attr1) {
            if(attr2) {
                Py_DECREF(attr2);
                Py_DECREF(attrs);
                if(desired == Py_EQ) {
                    Py_RETURN_FALSE;
                }
                Py_RETURN_TRUE;
            }
            continue;
        } else if (!attr2) {
            Py_DECREF(attr1);
            Py_DECREF(attrs);
            if(desired == Py_EQ) {
                Py_RETURN_FALSE;
            }
            Py_RETURN_TRUE;
        }
        int ret = PyObject_RichCompareBool(attr1, attr2, desired);
        Py_DECREF(attr1);
        Py_DECREF(attr2);
        if(0 > ret) {
            Py_DECREF(attrs);
            return NULL;
        } else if (0 == ret) {
            if(desired == Py_EQ) {
                Py_DECREF(attrs);
                Py_RETURN_FALSE;
            }
        } else if(desired == Py_NE) {
            Py_DECREF(attrs);
            Py_RETURN_TRUE;
        }
    }
    Py_DECREF(attrs);
    if(desired == Py_EQ) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject *
snakeoil_generic_equality_eq(PyObject *self, PyObject *other)
{
    return internal_generic_equality(self, other, Py_EQ);
}

static PyObject *
snakeoil_generic_equality_ne(PyObject *self, PyObject *other)
{
    return internal_generic_equality(self, other, Py_NE);
}

snakeoil_FUNC_BINDING("generic_eq", "snakeoil._klass.generic_eq",
    snakeoil_generic_equality_eq, METH_O|METH_COEXIST)

snakeoil_FUNC_BINDING("generic_ne", "snakeoil._klass.generic_ne",
    snakeoil_generic_equality_ne, METH_O)


static PyMethodDef snakeoil_mapping_get_def = {
    "get", snakeoil_mapping_get, METH_VARARGS, NULL};

static PyObject *
snakeoil_mapping_get_descr(PyObject *self, PyObject *obj, PyObject *type)
{
    return PyCFunction_New(&snakeoil_mapping_get_def, obj);
}

static PyTypeObject snakeoil_GetType = {
    PyObject_HEAD_INIT(NULL)
    0,                                               /* ob_size */
    "snakeoil_get_type",                              /* tp_name */
    sizeof(PyObject),                                /* tp_basicsize */
    0,                                               /* tp_itemsize */
    0,                                               /* tp_dealloc */
    0,                                               /* tp_print */
    0,                                               /* tp_getattr */
    0,                                               /* tp_setattr */
    0,                                               /* tp_compare */
    0,                                               /* tp_repr */
    0,                                               /* tp_as_number */
    0,                                               /* tp_as_sequence */
    0,                                               /* tp_as_mapping */
    0,                                               /* tp_hash  */
    0,                                               /* tp_call */
    0,                                               /* tp_str */
    0,                                               /* tp_getattro */
    0,                                               /* tp_setattro */
    0,                                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,                              /* tp_flags */
    "type of the get proxy",                         /* tp_doc */
    0,                                               /* tp_traverse */
    0,                                               /* tp_clear */
    0,                                               /* tp_richcompare */
    0,                                               /* tp_weaklistoffset */
    0,                                               /* tp_iter */
    0,                                               /* tp_iternext */
    0,                                               /* tp_methods */
    0,                                               /* tp_members */
    0,                                               /* tp_getset */
    0,                                               /* tp_base */
    0,                                               /* tp_dict */
    snakeoil_mapping_get_descr,                       /* tp_descr_get */
    0,                                               /* tp_descr_set */
};

static PyObject *
snakeoil_mapping_contains(PyObject *self, PyObject *key)
{
    if(!self) {
        PyErr_SetString(PyExc_TypeError,
            "need to be called with a mapping as the first arg");
        return NULL;
    }

    PyObject *ret = PyObject_GetItem(self, key);
    if(ret) {
        Py_DECREF(ret);
        ret = Py_True;
    } else if (!PyErr_ExceptionMatches(PyExc_KeyError)) {
        return NULL;
    } else {
        PyErr_Clear();
        ret = Py_False;
    }
    Py_INCREF(ret);
    return ret;
}

static PyMethodDef snakeoil_mapping_contains_def = {
    "contains", snakeoil_mapping_contains, METH_O|METH_COEXIST, NULL};

static PyObject *
snakeoil_mapping_contains_descr(PyObject *self, PyObject *obj, PyObject *type)
{
    return PyCFunction_New(&snakeoil_mapping_contains_def, obj);
}

static PyTypeObject snakeoil_ContainsType = {
    PyObject_HEAD_INIT(NULL)
    0,                                               /* ob_size */
    "snakeoil_contains_type",                         /* tp_name */
    sizeof(PyObject),                                /* tp_basicsize */
    0,                                               /* tp_itemsize */
    0,                                               /* tp_dealloc */
    0,                                               /* tp_print */
    0,                                               /* tp_getattr */
    0,                                               /* tp_setattr */
    0,                                               /* tp_compare */
    0,                                               /* tp_repr */
    0,                                               /* tp_as_number */
    0,                                               /* tp_as_sequence */
    0,                                               /* tp_as_mapping */
    0,                                               /* tp_hash  */
    0,                                               /* tp_call */
    0,                                               /* tp_str */
    0,                                               /* tp_getattro */
    0,                                               /* tp_setattro */
    0,                                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,                              /* tp_flags */
    "type of the contains proxy",                    /* tp_doc */
    0,                                               /* tp_traverse */
    0,                                               /* tp_clear */
    0,                                               /* tp_richcompare */
    0,                                               /* tp_weaklistoffset */
    0,                                               /* tp_iter */
    0,                                               /* tp_iternext */
    0,                                               /* tp_methods */
    0,                                               /* tp_members */
    0,                                               /* tp_getset */
    0,                                               /* tp_base */
    0,                                               /* tp_dict */
    snakeoil_mapping_contains_descr,                  /* tp_descr_get */
    0,                                               /* tp_descr_set */
};

PyDoc_STRVAR(
    snakeoil_klass_documentation,
    "misc cpython class functionality");


PyMODINIT_FUNC
init_klass()
{
    PyObject *m = Py_InitModule3("_klass", NULL, snakeoil_klass_documentation);
    if (!m)
        return;

    if (PyType_Ready(&snakeoil_GetAttrProxyType) < 0)
        return;

    if (PyType_Ready(&snakeoil_GetType) < 0)
        return;

    if (PyType_Ready(&snakeoil_ContainsType) < 0)
        return;

    if (PyType_Ready(&snakeoil_generic_equality_eq_type) < 0)
        return;

    if (PyType_Ready(&snakeoil_generic_equality_ne_type) < 0)
        return;

    if(!snakeoil_equality_attr) {
        if(!(snakeoil_equality_attr = PyString_FromString(
            "__attr_comparison__")))
            return;
    }

    PyObject *tmp;
    if (!(tmp = PyType_GenericNew(&snakeoil_GetType, NULL, NULL)))
        return;
    if (PyModule_AddObject(m, "get", tmp) == -1)
        return;

    if (!(tmp = PyType_GenericNew(&snakeoil_ContainsType, NULL, NULL)))
        return;
    if (PyModule_AddObject(m, "contains", tmp) == -1)
        return;

    Py_INCREF(&snakeoil_GetAttrProxyType);
    if (PyModule_AddObject(
            m, "GetAttrProxy", (PyObject *)&snakeoil_GetAttrProxyType) == -1)
        return;

    tmp = PyType_GenericNew(&snakeoil_generic_equality_eq_type, NULL, NULL);
    if(!tmp)
        return;
    if (PyModule_AddObject(m, "generic_eq", tmp) == -1)
        return;
    tmp = PyType_GenericNew(&snakeoil_generic_equality_ne_type, NULL, NULL);
    if(!tmp)
        return;
    if (PyModule_AddObject(m, "generic_ne", tmp) == -1)
        return;
}
