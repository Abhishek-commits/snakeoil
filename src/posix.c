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
#include <structmember.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

// only 2.5.46 kernels and up have this.
#ifndef MAP_POPULATE
#define MAP_POPULATE 0
#endif

static PyObject *snakeoil_stat_float_times = NULL;
static PyObject *snakeoil_empty_tuple = NULL;
static PyObject *snakeoil_readlines_empty_iter_singleton = NULL;


#define SKIP_SLASHES(ptr) while('/' == *(ptr)) (ptr)++;


static PyObject *
snakeoil_normpath(PyObject *self, PyObject *py_old_path)
{
    if(!PyString_CheckExact(py_old_path)) {
        PyErr_SetString(PyExc_TypeError,
            "old_path must be a str");
        return NULL;
    }
    Py_ssize_t path_len = PyString_GET_SIZE(py_old_path);
    if(!path_len)
        return PyString_FromString(".");

    char *path = PyString_AS_STRING(py_old_path);

    PyObject *new_obj = PyString_FromStringAndSize(NULL, path_len);
    if(!new_obj)
        return new_obj;
    char *new_path = PyString_AS_STRING(new_obj);
    char *write = new_path;
    int depth=0;
    int is_absolute = '/' == *path;

    if(is_absolute) {
        depth--;
    }

    while('\0' != *path) {
            if ('/' == *path) {
                *write = '/';
                write++;
                SKIP_SLASHES(path);
                depth++;
            } else if('.' == *path) {
                if('.' == path[1] && ('/' == path[2] || '\0' == path[2])) {
                    if(1 == depth) {
                        if(is_absolute) {
                            write = new_path;
                        } else {
                            // why -2?  because write is at an empty char.
                            // we need to jump back past it and /
                            write-=2;
                            while('/' != *write)
                                write--;
                        }
                        write++;
                        depth = 0;
                    } else if(depth) {
                        write-=2;
                        while('/' != *write)
                            write--;
                        write++;
                        depth--;
                    } else {
                        if(is_absolute) {
                            write = new_path + 1;
                        } else {
                            write[0] = '.';
                            write[1] = '.';
                            write[2] = '/';
                            write += 3;
                        }
                    }
                    path+= 2;
                    SKIP_SLASHES(path);
                } else if('/' == path[1]) {
                    path += 2;
                    SKIP_SLASHES(path);
                } else if('\0' == path[1]) {
                    path++;
                } else {
                    *write = '.';
                    path++;
                    write++;
                }
            } else {
                while('/' != *path && '\0' != *path) {
                    *write = *path;
                    write++;
                    path++;
                }
            }
    }
    if(write -1 > new_path && '/' == write[-1])
        write--;

    _PyString_Resize(&new_obj, write - new_path);
    return new_obj;

}

static PyObject *
snakeoil_join(PyObject *self, PyObject *args)
{
    if(!args) {
        PyErr_SetString(PyExc_TypeError, "requires at least one path");
        return NULL;
    }
    PyObject *fast = PySequence_Fast(args, "arg must be a sequence");
    if(!fast)
        return NULL;
    Py_ssize_t end = PySequence_Fast_GET_SIZE(fast);
    if(!end) {
        PyErr_SetString(PyExc_TypeError,
            "join takes at least one arguement (0 given)");
        return NULL;
    }

    PyObject **items = PySequence_Fast_ITEMS(fast);
    Py_ssize_t start = 0, len, i = 0;
    char *s;
    int leading_slash = 0;
    // find the right most item with a prefixed '/', else 0.
    for(; i < end; i++) {
        if(!PyString_CheckExact(items[i])) {
            PyErr_SetString(PyExc_TypeError, "all args must be strings");
            Py_DECREF(fast);
            return NULL;
        }
        s = PyString_AsString(items[i]);
        if('/' == *s) {
            leading_slash = 1;
            start = i;
        }
    }
    // know the relevant slice now; figure out the size.
    len = 0;
    char *s_start;
    for(i = start; i < end; i++) {
        // this is safe because we're using CheckExact above.
        s_start = s = PyString_AS_STRING(items[i]);
        while('\0' != *s)
            s++;
        if(s_start == s)
            continue;
        len += s - s_start;
        char *s_end = s;
        if(i + 1 != end) {
            // cut the length down for trailing duplicate slashes
            while(s != s_start && '/' == s[-1])
                s--;
            // allocate for a leading slash if needed
            if(s_end == s && (s_start != s ||
                (s_end == s_start && i != start))) {
                len++;
            } else if(s_start != s) {
                len -= s_end - s -1;
            }
        }
    }

    // ok... we know the length.  allocate a string, and copy it.
    PyObject *ret = PyString_FromStringAndSize(NULL, len);
    if(!ret)
        return NULL;
    char *buf = PyString_AS_STRING(ret);
    if(leading_slash) {
        *buf = '/';
        buf++;
    }
    for(i = start; i < end; i++) {
        s_start = s = PyString_AS_STRING(items[i]);
        if(i == start && leading_slash) {
            // a slash is inserted anywas, thus we skip one ahead
            // so it doesn't gain an extra.
            s_start++;
            s = s_start;
        }

       if('\0' == *s)
            continue;
        while('\0' != *s) {
            *buf = *s;
            buf++;
            if('/' == *s) {
                char *tmp_s = s + 1;
                SKIP_SLASHES(s);
                if('\0' == *s) {
                    if(i + 1  != end) {
                        buf--;
                    } else {
                        // copy the cracked out trailing slashes on the
                        // last item
                        while(tmp_s < s) {
                            *buf = '/';
                            buf++;
                            tmp_s++;
                        }
                    }
                    break;
                } else {
                    // copy the cracked out intermediate slashes.
                    while(tmp_s < s) {
                        *buf = '/';
                        buf++;
                        tmp_s++;
                    }
                }
            } else
                s++;
        }
        if(i + 1 != end) {
            *buf = '/';
            buf++;
        }
    }
    *buf = '\0';
    Py_DECREF(fast);
    return ret;
}

// returns 0 on success opening, 1 on ENOENT but ignore, and -1 on failure
// if failure condition, appropriate exception is set.

static inline int
snakeoil_read_open_and_stat(PyObject *path,
    int *fd, struct stat *st)
{
    errno = 0;
    if((*fd = open(PyString_AsString(path), O_RDONLY)) >= 0) {
        int ret = fstat(*fd, st);
        if(!ret) {
            return 0;
        }
    }
    return 1;
}

static inline int
handle_failed_open_stat(int fd, PyObject *path, PyObject *swallow_missing)
{
    if(fd < 0) {
        if(errno == ENOENT) {
            if(swallow_missing) {
                if(PyObject_IsTrue(swallow_missing)) {
                    errno = 0;
                    return 0;
                }
                if(PyErr_Occurred())
                    return 1;
            }
        }
        PyErr_SetFromErrnoWithFilenameObject(PyExc_IOError, path);
        return 1;
    }
    PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
    if(close(fd))
        PyErr_SetFromErrnoWithFilenameObject(PyExc_IOError, path);
    return 1;
}

static PyObject *
snakeoil_readfile(PyObject *self, PyObject *args)
{
    PyObject *path, *swallow_missing = NULL;
    if(!args || !PyArg_ParseTuple(args, "S|O:readfile", &path,
        &swallow_missing)) {
        return NULL;
    }
//    Py_ssize_t size;
    int fd;
    struct stat st;
    Py_BEGIN_ALLOW_THREADS
    if(snakeoil_read_open_and_stat(path, &fd, &st)) {
        Py_BLOCK_THREADS
        if(handle_failed_open_stat(fd, path, swallow_missing))
            return NULL;
        Py_RETURN_NONE;
    }
    Py_END_ALLOW_THREADS

    int ret = 0;
    PyObject *data = PyString_FromStringAndSize(NULL, st.st_size);

    Py_BEGIN_ALLOW_THREADS
    errno = 0;
    if(data) {
        ret = read(fd, PyString_AS_STRING(data), st.st_size) != st.st_size ? 1 : 0;
    }
    ret += close(fd);
    Py_END_ALLOW_THREADS

    if(ret) {
        Py_CLEAR(data);
        data = PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
    }
    return data;
}

typedef struct {
    PyObject_HEAD
} snakeoil_readlines_empty_iter;

static PyObject *
snakeoil_readlines_empty_iter_get_mtime(snakeoil_readlines_empty_iter *self)
{
    Py_RETURN_NONE;
}

static int
snakeoil_readlines_empty_iter_set_mtime(snakeoil_readlines_empty_iter *self,
    PyObject *v, void *closure)
{
    PyErr_SetString(PyExc_AttributeError, "mtime is immutable");
    return -1;
}

static PyObject *
snakeoil_readlines_empty_iter_next(snakeoil_readlines_empty_iter *self)
{
    PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}

struct PyGetSetDef snakeoil_readlines_empty_iter_getsetters[] = {
    snakeoil_GETSET(snakeoil_readlines_empty_iter, "mtime", mtime),
    {NULL}
};

static PyTypeObject snakeoil_readlines_empty_iter_type = {
    PyObject_HEAD_INIT(NULL)
    0,                                               /* ob_size */
    "readlines.empty_iter",                          /* tp_name */
    sizeof(snakeoil_readlines_empty_iter),            /* tp_size */
    0,                                               /* tp_itemsize*/
    0,                                               /* tp_dealloc*/
    0,                                               /* tp_print*/
    0,                                               /* tp_getattr*/
    0,                                               /* tp_setattr*/
    0,                                               /* tp_compare*/
    0,                                               /* tp_repr*/
    0,                                               /* tp_as_number*/
    0,                                               /* tp_as_sequence*/
    0,                                               /* tp_as_mapping*/
    0,                                               /* tp_hash */
    (ternaryfunc)0,                                  /* tp_call*/
    (reprfunc)0,                                     /* tp_str*/
    0,                                               /* tp_getattro*/
    0,                                               /* tp_setattro*/
    0,                                               /* tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,                              /* tp_flags*/
    0,                                               /* tp_doc */
    (traverseproc)0,                                 /* tp_traverse */
    (inquiry)0,                                      /* tp_clear */
    (richcmpfunc)0,                                  /* tp_richcompare */
    0,                                               /* tp_weaklistoffset */
    (getiterfunc)PyObject_SelfIter,                  /* tp_iter */
    (iternextfunc)snakeoil_readlines_empty_iter_next, /* tp_iternext */
    0,                                               /* tp_methods */
    0,                                               /* tp_members */
    snakeoil_readlines_empty_iter_getsetters,         /* tp_getset */
};

typedef struct {
    PyObject_HEAD
    char *start;
    char *end;
    char *map;
    int fd;
    int strip_newlines;
    time_t mtime;
    unsigned long mtime_nsec;
    PyObject *fallback;
} snakeoil_readlines;

static PyObject *
snakeoil_readlines_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    PyObject *path, *swallow_missing = NULL, *strip_newlines = NULL;
    PyObject *none_on_missing = NULL;
    snakeoil_readlines *self = NULL;
    if(kwargs && PyDict_Size(kwargs)) {
        PyErr_SetString(PyExc_TypeError,
            "readlines.__new__ doesn't accept keywords");
        return NULL;
    } else if (!PyArg_ParseTuple(args, "S|OOOO:readlines.__new__",
        &path, &strip_newlines, &swallow_missing, &none_on_missing)) {
        return NULL;
    }

    int fd;
    struct stat st;
//    Py_ssize_t size;
    void *ptr = NULL;
    PyObject *fallback = NULL;
    Py_BEGIN_ALLOW_THREADS
    errno = 0;
    if(snakeoil_read_open_and_stat(path, &fd, &st)) {
        Py_BLOCK_THREADS

        if(handle_failed_open_stat(fd, path, swallow_missing))
            return NULL;

        // return an empty tuple, and let them iter over that.
        if(none_on_missing && PyObject_IsTrue(none_on_missing)) {
            Py_RETURN_NONE;
        }

        Py_INCREF(snakeoil_readlines_empty_iter_singleton);
        return snakeoil_readlines_empty_iter_singleton;
    }
    if(st.st_size >= 0x4000) {
        ptr = (char *)mmap(NULL, st.st_size, PROT_READ,
            MAP_SHARED|MAP_NORESERVE|MAP_POPULATE, fd, 0);
        if(ptr == MAP_FAILED)
            ptr = NULL;
    } else {
        Py_BLOCK_THREADS
        fallback = PyString_FromStringAndSize(NULL, st.st_size);
        Py_UNBLOCK_THREADS
        if(fallback) {
            errno = 0;
            ptr = (read(fd, PyString_AS_STRING(fallback), st.st_size) != st.st_size) ?
                MAP_FAILED : NULL;
        }
        int ret = close(fd);
        if(ret) {
            Py_CLEAR(fallback);
            PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
            Py_BLOCK_THREADS
            return NULL;
        } else if(!fallback) {
            Py_BLOCK_THREADS
            return NULL;
        }
    }
    Py_END_ALLOW_THREADS

    if(ptr == MAP_FAILED) {
        PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
        if(close(fd))
            PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
        Py_CLEAR(fallback);
        return NULL;
    }

    self = (snakeoil_readlines *)type->tp_alloc(type, 0);
    if(!self) {
        // you've got to be kidding me...
        if(ptr) {
            munmap(ptr, st.st_size);
            close(fd);
            errno = 0;
        } else {
            Py_DECREF(fallback);
        }
        if(self) {
            Py_DECREF(self);
        }
        return NULL;
    }
    self->fallback = fallback;
    self->map = ptr;
    self->mtime = st.st_mtime;
#ifdef HAVE_STAT_TV_NSEC
    self->mtime_nsec = st.st_mtim.tv_nsec;
#else
    self->mtime_nsec = 0;
#endif
    if (ptr) {
        self->start = ptr;
        self->fd = fd;
    } else {
        self->start = PyString_AS_STRING(fallback);
        self->fd = -1;
    }
    self->end = self->start + st.st_size;

    if(strip_newlines) {
        if(strip_newlines == Py_True) {
            self->strip_newlines = 1;
        } else if (strip_newlines == Py_False) {
            self->strip_newlines = 0;
        } else {
            self->strip_newlines = PyObject_IsTrue(strip_newlines) ? 1 : 0;
            if(PyErr_Occurred()) {
                Py_DECREF(self);
                return NULL;
            }
        }
    } else
        self->strip_newlines = 1;
    return (PyObject *)self;
}

static void
snakeoil_readlines_dealloc(snakeoil_readlines *self)
{
    if(self->fallback) {
        Py_DECREF(self->fallback);
    } else if(self->map) {
        if(munmap(self->map, self->end - self->map))
            // swallow it, no way to signal an error
            errno = 0;
        if(close(self->fd))
            // swallow it, no way to signal an error
            errno = 0;
    }
    self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
snakeoil_readlines_iternext(snakeoil_readlines *self)
{
    if(self->start == self->end) {
        // at the end, thus return
        return NULL;
    }
    char *p = self->start;
    assert(self->end);
    assert(self->start);
    assert(self->map || self->fallback);
    assert(self->end > self->start);

    p = memchr(p, '\n', self->end - p);
    if(!p)
        p = self->end;

    PyObject *ret;
    if(self->strip_newlines) {
        ret = PyString_FromStringAndSize(self->start, p - self->start);
    } else {
        if(p == self->end)
            ret = PyString_FromStringAndSize(self->start, p - self->start);
        else
            ret = PyString_FromStringAndSize(self->start, p - self->start + 1);
    }
    if(p != self->end) {
        p++;
    }
    self->start = p;
    return ret;
}

static int
snakeoil_readlines_set_mtime(snakeoil_readlines *self, PyObject *v,
    void *closure)
{
    PyErr_SetString(PyExc_AttributeError, "mtime is immutable");
    return -1;
}

static PyObject *
snakeoil_readlines_get_mtime(snakeoil_readlines *self)
{
    PyObject *ret = PyObject_CallFunctionObjArgs(snakeoil_stat_float_times, NULL);
    if(!ret)
        return NULL;
    int is_float;
    if(ret == Py_True) {
        is_float = 1;
    } else if (ret == Py_False) {
        is_float = 0;
    } else {
        is_float = PyObject_IsTrue(ret);
        if(is_float == -1) {
            Py_DECREF(ret);
            return NULL;
        }
    }
    Py_DECREF(ret);
    if(is_float)
        return PyFloat_FromDouble(self->mtime + 1e-9 * self->mtime_nsec);
#if SIZEOF_TIME_T > SIZEOF_LONG
    return PyLong_FromLong((Py_LONG_LONG)self->mtime);
#else
    return PyInt_FromLong((long)self->mtime);
#endif
}

static PyGetSetDef snakeoil_readlines_getsetters[] = {
snakeoil_GETSET(snakeoil_readlines, "mtime", mtime),
    {NULL}
};

PyDoc_STRVAR(
    snakeoil_readlines_documentation,
    "readline(path [, strip_newlines [, swallow_missing [, none_on_missing]]])"
    " -> iterable yielding"
    " each line of a file\n\n"
    "if strip_newlines is True, the trailing newline is stripped\n"
    "if swallow_missing is True, for missing files it returns an empty "
    "iterable\n"
    "if none_on_missing and the file is missing, return None instead"
    );


static PyTypeObject snakeoil_readlines_type = {
    PyObject_HEAD_INIT(NULL)
    0,                                               /* ob_size*/
    "snakeoil.osutils._posix.readlines",             /* tp_name*/
    sizeof(snakeoil_readlines),                       /* tp_basicsize*/
    0,                                               /* tp_itemsize*/
    (destructor)snakeoil_readlines_dealloc,           /* tp_dealloc*/
    0,                                               /* tp_print*/
    0,                                               /* tp_getattr*/
    0,                                               /* tp_setattr*/
    0,                                               /* tp_compare*/
    0,                                               /* tp_repr*/
    0,                                               /* tp_as_number*/
    0,                                               /* tp_as_sequence*/
    0,                                               /* tp_as_mapping*/
    0,                                               /* tp_hash */
    (ternaryfunc)0,                                  /* tp_call*/
    (reprfunc)0,                                     /* tp_str*/
    0,                                               /* tp_getattro*/
    0,                                               /* tp_setattro*/
    0,                                               /* tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,                              /* tp_flags*/
    snakeoil_readlines_documentation,                 /* tp_doc */
    (traverseproc)0,                                 /* tp_traverse */
    (inquiry)0,                                      /* tp_clear */
    (richcmpfunc)0,                                  /* tp_richcompare */
    0,                                               /* tp_weaklistoffset */
    (getiterfunc)PyObject_SelfIter,                  /* tp_iter */
    (iternextfunc)snakeoil_readlines_iternext,        /* tp_iternext */
    0,                                               /* tp_methods */
    0,                                               /* tp_members */
    snakeoil_readlines_getsetters,                    /* tp_getset */
    0,                                               /* tp_base */
    0,                                               /* tp_dict */
    0,                                               /* tp_descr_get */
    0,                                               /* tp_descr_set */
    0,                                               /* tp_dictoffset */
    (initproc)0,                                     /* tp_init */
    0,                                               /* tp_alloc */
    snakeoil_readlines_new,                           /* tp_new */
};

static PyMethodDef snakeoil_posix_methods[] = {
    {"normpath", (PyCFunction)snakeoil_normpath, METH_O,
        "normalize a path entry"},
    {"join", snakeoil_join, METH_VARARGS,
        "join multiple path items"},
    {"readfile", snakeoil_readfile, METH_VARARGS,
        "fast read of a file: requires a string path, and an optional bool "
        "indicating whether to swallow ENOENT; defaults to false"},
    {NULL}
};

PyDoc_STRVAR(
    snakeoil_posix_documentation,
    "cpython posix path functionality");

PyMODINIT_FUNC
init_posix()
{
    PyObject *s = PyString_FromString("os");
    if(!s)
        return;

    PyObject *mos = PyImport_Import(s);
    Py_DECREF(s);
    if(!mos)
        return;
    snakeoil_stat_float_times = PyObject_GetAttrString(mos, "stat_float_times");
    Py_DECREF(mos);
    if(!snakeoil_stat_float_times)
        return;

    snakeoil_empty_tuple = PyTuple_New(0);
    if(!snakeoil_empty_tuple)
        return;

    PyObject *m = Py_InitModule3("_posix", snakeoil_posix_methods,
                                 snakeoil_posix_documentation);
    if (!m)
        return;

    if (PyType_Ready(&snakeoil_readlines_type) < 0)
        return;

    if (PyType_Ready(&snakeoil_readlines_empty_iter_type) < 0)
        return;

    Py_INCREF(&snakeoil_readlines_empty_iter_type);
    snakeoil_readlines_empty_iter_singleton = _PyObject_New(
        &snakeoil_readlines_empty_iter_type);


    Py_INCREF(&snakeoil_readlines_type);
    if (PyModule_AddObject(
            m, "readlines", (PyObject *)&snakeoil_readlines_type) == -1)
        return;

    /* Success! */
}
