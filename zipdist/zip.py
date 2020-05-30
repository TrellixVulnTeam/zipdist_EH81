import json
import os
import numpy as np
import pandas as pd
import tarfile
import sys
import warnings


class Zipdist():
    """ 
    A parent class that bestows the ability to rebuild child classes from a .tar.gz file.

    This would be useful for saving and reloading a python object that contains numpy arrays
    and pandas DataFrames.

    Attributes
    ----------
    name : str
        Name of instance, which can be used as default for storage directory
    _complex_attributes : dict      
        Store information for retrieval of complex attributes are those that must be read from .csv or .binary files
    _simple_attributes : dict    
        Store keys and contentes of simple attributes, those that can be stored in a json file.

    Example 
    -------


    .. code-block:: python


        class Y(zipdist):
        def __init__(self, name):
            self.name = name
            self.year = None
            self._ready()

        y = Y('Simpsons')
        y.years = [2020,2019]
        y.bart = np.zeros(10)
        y.lisa = pd.DataFrame([{"Pi":3.1415,"e":2.7182}])
        y._save()
        assert os.path.isfile("Simpsons.tar.gz")

        # Create a New Object, None of the prior attributes exists
        assert os.path.isfile("Simpsons.tar.gz")
        y2 = Y("Simpsons")
        assert 'bart' not in y2.__dict__.keys()
        assert 'years' not in y2.__dict__.keys()

        # But you can rebuilt them easily with zipdist
        y2._build(dest="Simpsons", dest_tar = "Simpsons.tar.gz")
        assert isinstance(y2.bart, np.ndarray)
        assert isinstance(y2.lise, pd.DataFrames)

    """
    def __init__(self, name = "testname"):
        self.name = name

    def _ready(self):
        sys.stdout.write("zipdist : Yahs Queen\n")
 
    def _get_attributes(self):
        return list(self.__dict__.keys())

    def _get_attribute_types(self):
        return {k:type(v) for k,v in self.__dict__.items() }


    def _save(self, dest = None, dest_tar = None, verbose = True):
        """
        Saves atttributes of a Python object into a <dest> destination folder
        then tar and gz those files. 
        
        Parameters
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        dest_tar : string
            name of the tar file to hold the object dest.tar.gz
        verbose : bool
            write status updates to sys.stdout if True
        
        Notes
        -----
        Currently only Pandas DataFrame and Numpy ndarrays are supported as 
        special attribute types. 
        """
        if dest is None:
            dest = str(self.name)
        if dest_tar is None:
            dest_tar = f"{dest}.tar.gz"
        self._complex_attributes = dict()
        self._simple_attributes = dict()
        # make <dest> destination folder if it does not exist
        self._make_dest_directory(dest = dest, verbose = verbose)
        # save numpy attributes as binary files into <dest> destination
        self._save_numpy_attributes(dest = dest, verbose = verbose)
        # save pandas attributes as binary files into <dest> destination
        self._save_pandas_attributes(dest = dest, verbose = verbose)
        # save a json dictionary so we can recover complex attributes, and know their types
        self._save_complex_attributes(dest = dest)
        # save simple attributes as a json
        self._save_simple_attributes(dest = dest)
        # tar and gz all the abject attributes
        self._save_as_tar_gz(dest = dest, dest_tar = dest_tar)

    def _build(self, dest=None, dest_tar=None, verbose = True, reload = True):
        """
        Builds attributes of a python class using a .tar.gz directory

        Parameters
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        dest_tar : string
            name of the tar file to hold the object dest.tar.gz
        verbose : bool
            write status updates to sys.stdout if True
        reload : bool 
            If True, _build loads simple and complex attribute. 
            If False, individual attrs can be installed one by one.

        Notes
        -----
        _build adds attributes ._complex_attributes and ._simple_attributes 
        which its methods then use to populate object attribute fields
        using the specified tar.gz directory. 

        """
        self._complex_attributes = dict()
        self._simple_attributes = dict()
        if dest is None:
            dest = str(self.name)
        if dest_tar is None:
            dest_tar = f"{dest}.tar.gz"
        self.dest = dest
        self.dest_tar = dest_tar
        # extracts a tarfile
        self._extract_tarfile( dest_tar = dest_tar , verbose = verbose)
        # open the recovery_attributes.json and get information on attribute names and types
        # this will create self.recovery_attributes which can be used to recover the numpy and pandas attributes
        self._get_complex_attribute_definitions(dest = dest,  dest_tar = dest_tar, verbose = verbose)
        self._get_simple_attribute_definitions(dest = dest,  dest_tar = dest_tar, verbose = verbose)
        if reload:
            self._reload()

    def _reload(self):
        """

        Wrapper for both simple and complex attribute reloads
        
        Notes
        -----
        Complex attributes are those that must be read from .csv or .binary files
        Simple attributes are those that can be stored in json file.
        
        """
        self._reload_simple_all()
        self._reload_complex_all()
    
    def _reload_simple_all(self, verbose = True):
        """
        Class method that loops through the _simple_attributes dictionary and 
        sets attributes values from that dictionary

        Parameters
        ----------
        verbose : bool
            if true, report update of attribute value

        Notes
        -----
        Simple attributes are those that can be stored in json file.
        """
        for k, v in self._simple_attributes.items():
            if k in ["_complex_attributes", "_simple_attributes"]:
                continue
            if v is None:
                continue 
            setattr(self, k, v)
            if verbose: sys.stdout.write(f"\tsetting simple attribute {k} to {v}\n")    
            
    def _reload_complex_all(self, verbose = True):
        """ 
        Class method that loops through the _complex_attributes dictionary 
        and sets attributes with calls to ._reload_complex()

        Parameters
        ----------
        verbose : bool
            if true, report update of attribute value
        """
        for k in self._complex_attributes.keys():
            self._reload_complex(k, verbose = verbose)

    
    def _reload_complex(self, k, verbose = True):
        """
        Reloads only a single complex attribute with key <k>

        k : str
            key name for the complex attribute 
        verbose : bool
            if true, report update of attribute value

        Notes
        -----
        Complex attributes require a function to read from a binary or .csv file 
        with the .tar.gz directory

        """
        v = self._complex_attributes[k]
        filename   = v['filename']
        filetype   = v['filetype']
        fileformat = v['fileformat']

        def _ndarray_from_csv(fn):
            return np.genfromtxt(fn, delimiter=',')
        
        def _dataframe_from_csv(fn):
            return pd.read_csv(fn, sep= ",")

        try:
            func = {"np.ndarray"   : _ndarray_from_csv,
                    "pd.DataFrame": _dataframe_from_csv}[filetype]
            x = func(filename)
            setattr(self, k, x)
            if verbose: sys.stdout.write(f"\tsetting [{fileformat}] to [{filetype}] for attribute {k} from: {filename}\n")
        except KeyError:
            warnings.warn(f"Could not reload {k}, {filename} had unrecognized {filetype}")

    def _reload_simple(self, k, verbose = True):
        """ 
        Reloads only a single simple attribute with key <k>

        k : str
            key name for the complex attribute 
        verbose : bool
            if true, report update of attribute value
        """
        try:
            setattr(self, k, self._simple_attributes[k])
            if verbose: sys.stdout.write(f"\tsetting attribute {k}\n") 
        except KeyError:
             warnings.warn(f"Could not reload simple attribute {k}")

    def _make_dest_directory(self, dest, verbose = True):
        """ If /dest does not exist create it """
        if not os.path.isdir(dest):
            if verbose: sys.stdout.write(f"\tMaking directory {dest}/.\n")
            os.mkdir(dest)

    def _save_numpy_attributes(self, dest = None, verbose = True):
        """
        Save Numpy ndarray attribute as .csv file to the dest folder

        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        """
        self._get_attributes()
        for k in self._get_attributes():
            if isinstance(getattr(self,k), np.ndarray):
                f = os.path.join(dest, f"{k}.cs")
                if verbose: sys.stdout.write(f"\tSaving {k} to .csv : {f}\n")
                getattr(self,k).tofile(file= f, sep = ",")
                # keep record of filename associated with each attr
                self._complex_attributes[k] = {"filename": f,  "filetype" : "np.ndarray", "fileformat":"csv"} # "type" : type(getattr(self,k)) 
    
    def _save_pandas_attributes(self, dest = None, verbose = True):
        """
        Save Pandas DataFrame attribute as .csv file to the dest folder

        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        """
        for k in self._get_attributes():
            if isinstance(getattr(self,k), pd.DataFrame):
                f = os.path.join(dest, f"{k}.csv")
                if verbose: sys.stdout.write(f"\tSaving {k} to .csv : {f}\n")
                getattr(self,k).to_csv(f, sep = "," , index =False)
                # keep record of filename associated with each attr
                self._complex_attributes[k]={"filename":f,  "filetype" : "pd.DataFrame", "fileformat":"csv"} #"type" : type(getattr(self,k))
    
    def _save_simple_attributes(self, dest = None, verbose= True):
        """
        Save a json dictionary so we can recover 
        simple  attributes, such as ints, strings, and lists.

        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        verbose : bool
            write status updates to sys.stdout if True
        """
        f = os.path.join(dest, 'simple_attributes.json')
        with open(f, 'w') as fp:
            json.dump(self.__dict__, fp, default = lambda x : None) # note the lambda function deals with things that can't be serialized
            if verbose: sys.stdout.write(f"\tSaving JSON with simple attribute defintions : {f}\n")
    
    def _save_complex_attributes(self, dest = None, verbose = True):
        """
        Save a json dictionary so we can recover 
        complex attributes, and know their types 

         Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        verbose : bool
            write status updates to sys.stdout if True
        
        """
        f = os.path.join(dest, 'complex_attributes.json')
        with open(f, 'w') as fp:
            json.dump(self._complex_attributes, fp)
            if verbose: sys.stdout.write(f"\tSaving JSON with complex attribute defintions : {f}\n")

    def _save_as_tar_gz(self, dest = None, dest_tar = None):
        """ 
        tar and gz all the object attributes
        
        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        dest_tar : str
            name of the tar file to hold the object dest.tar.gz

        """
        with tarfile.open(dest_tar, "w:gz") as tar:
            sys.stdout.write(f"\tCombining saved files in : [{dest_tar}].\n")
            tar.add(dest, arcname=os.path.basename(dest))
            
    def _extract_tarfile(self, dest_tar = None, verbose = True):
        """
        Extracts the tar file with name <dest_tar>
        
        Parameters
        ----------
        dest_tar : str
            name of the tar file to hold the object dest.tar.gz

        """
        with tarfile.open(dest_tar , "r:gz") as tar:
            tar.extractall()
            if verbose: 
                contents = tar.getnames()
                sys.stdout.write(f"\tContents of {dest_tar} :\n\t\t")
                contents_newlines = '\n\t\t'.join(map(str, contents))
                sys.stdout.write(f"{contents_newlines}\n")

    def _get_complex_attribute_definitions(self, dest = None, dest_tar = None, verbose = True):
        """
        Loads from complex_attributes.json file a dictioanary of 
        simple (i.e., non-serializable as json) attribute values.

        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        dest_tar : str
            name of the tar file to hold the object dest.tar.gz
        verbose : bool
            write status updates to sys.stdout if True
        
        """
        complex_attributes_json = os.path.join(dest,'complex_attributes.json')
        assert os.path.isfile(complex_attributes_json)
        with open(complex_attributes_json, 'r') as fp:
            # loads the 
            complex_attributes = json.load(fp)
            self._complex_attributes =  complex_attributes 

    def _get_simple_attribute_definitions(self, dest = None, dest_tar = None, verbose = True):
        """
        Loads from simple_attributes.json file a dictioanary of 
        simple (i.e., serializable as json) attribute values.

        Parameters 
        ----------
        dest : str
            e.g., obj_name/ specifies the folder where numpy and pandas files are saved
        dest_tar : str
            name of the tar file to hold the object dest.tar.gz
        verbose : bool
            write status updates to sys.stdout if True
        
        """
        simple_attributes_json = os.path.join(dest,'simple_attributes.json')
        assert os.path.isfile(simple_attributes_json)
        with open(simple_attributes_json, 'r') as fp:
            # loads the 
            simple_attributes = json.load(fp)
            self._simple_attributes = simple_attributes 
















