# Test cellpose
# Run in cellpose environment
# Slow on full size images
# You can either the images before predictionm, but this requires resizing the mask.
# Compare to see which option is faster.

# Imports of general purpose libraries
from skimage.transform import resize
from skimage.io import imread, imsave
import numpy as np
from tqdm import tqdm
import time
import mxnet as mx
import matplotlib.pyplot as plt
import pathlib
from pathlib import Path

# Imports of CellPose specific libraries
from cellpose import models, utils
from cellpose import plot, transforms

from segwrap.utils_general import log_message
from segwrap.utils_general import create_output_path


# Function: check if GPU working, and if so use it
def check_device(gpu_number=0, callback_log=None):
    """ Check on which device (GPU or CPU) CellPose will be running. 

    Parameters
    ----------
    gpu_number : int, optional
        Index of GPU to be tested, by default 0
    """
    use_gpu = utils.use_gpu(gpu_number=gpu_number)
    if use_gpu:
        log_message('CellPose will be USING GPU', callback_fun=callback_log)
        device = mx.gpu()
    else:
        log_message('CellPose will be USING CPU', callback_fun=callback_log)
        device = mx.cpu()

    return device


# Call predict function
def cellpose_predict(data, config, path_save, callback_log=None):
    """ Perform prediction with CellPose. 

    Parameters
    ----------
    data : dict
        Contains data on which prediction should be performed. 
    config : dict
        Configuration of CellPose prediction. 
    path_save : pathline Path object
        Path where results will be saved. 
    """

    # Get data
    imgs = data['imgs']
    file_names = data['file_names']
    sizes_orginal = data['sizes_orginal']
    channels = data['channels']
    new_size = data['new_size']
    obj_name = data['obj_name']

    # Get config
    model_type = config['model_type']
    obj_size = config['obj_size']
    device = config['device']

    log_message(f'\nPerforming segmentation of {obj_name}\n', callback_fun=callback_log)

    start_time = time.time()

    if not path_save.is_dir():
        path_save.mkdir()

    # Perform segmentation with CellPose

    model = models.Cellpose(device, model_type=model_type )  # model_type can be 'cyto' or 'nuclei'
    masks, flows, styles, diams = model.eval(imgs, rescale=30./obj_size, channels=channels, net_avg=False, threshold=0.4)

    # Display and save 
    log_message(f'\n ... creating outputs ...\n', callback_fun=callback_log)
    n_img = len(imgs)

    for idx in tqdm(range(n_img)):
        img = transforms.reshape(imgs[idx], channels)
        file_name = file_names[idx]

        img = plot.rgb_image(img)
        maski = masks[idx]
        flowi = flows[idx][0]

        # Save overview image
        fig = plt.figure(figsize=(12, 3))
        plot.show_segmentation(fig, img, maski, flowi)
        plt.tight_layout()

        plt.savefig(path_save / f'segmentation__{obj_name}__{file_name.stem}.png', dpi=600)
        plt.close()

        # Save mask and flow images
        imsave(path_save / f'flow__{obj_name}__{file_name.stem}.png', flowi, check_contrast=False)

        if new_size:
            mask_full = resize_mask(maski, sizes_orginal[idx])

            imsave(path_save / f'mask__{obj_name}__{file_name.stem}.png', mask_full.astype('uint16'), check_contrast=False)
            imsave(path_save / f'mask_resize__{obj_name}__{file_name.stem}.png', maski.astype('uint16'), check_contrast=False)
        else:
            imsave(path_save / f'mask__{obj_name}__{file_name.stem}.png', maski.astype('uint16'), check_contrast=False)

    log_message(f"Segmentation of provided images finished ({(time.time() - start_time)}s)", callback_fun=callback_log)
    # log_message("\n--- %s seconds ---" % ), callback_fun=callback_log)    


# Function to load and segment nuclei images individually 
def segment_obj_indiv(path_scan, obj_name, str_channel, img_ext, new_size, obj_size, model_type, path_save, input_subfolder=None, callback_log=None, callback_status=None, callback_progress=None):
    """ Will recursively search folder for images to be analyzed!

    Parameters
    ----------
    path_scan : [type]
        [description]
    str_nuclei : [type]
        [description]
    img_ext : [type]
        [description]
    new_size : [type]
        [description]
    size_nuclei : [type]
        [description]
    model_nuclei : [type]
        [description]
    path_save : pathlin object or string
        Path to save results,
        - If Pathlib object, then this absolute path is used.
        - If 'string' a replacement operation on the provided name of the data path will be applied (see create_output_path).
    input_subfolder : str
        Name of subfolder that contains results. If specified ONLY files in this folder will be processed.
    callback_log : [type], optional
        [description], by default None
    callback_status : [type], optional
        [description], by default None
    callback_progress : [type], optional
        [description], by default None

    Returns
    -------
    [type]
        [description]
    """

    # Print all input parameters
    log_message(f"Function (segment_obj_indiv) called with: {str(locals())} ", callback_fun=callback_log)

    print('what?')
    # Configurations
    device = check_device(callback_log=callback_log)

    config = {'model_type': model_type,
              'obj_size': obj_size,
              'device': device}

    channels = [0, 1]

    # Use provided absolute user-path to save images.
    if isinstance(path_save, pathlib.PurePath):
        path_save_results = path_save
        if not path_save_results.is_dir():
            path_save_results.mkdir(parents=True)

    else:
        path_save_str_replace = path_save

    if not path_scan.is_dir():
        log_message(f'Path {path_scan} does not exist.', callback_fun=callback_log) 
        return

    # Search for file to be analyzed
    log_message(f'\nLoading images and segment them on the fly', callback_fun=callback_log)
    files_proc = []
    for path_img in path_scan.rglob(f'*{str_channel}*{img_ext}'):
        if input_subfolder:
            if path_img.parts[-2] == input_subfolder:
                files_proc.append(path_img)
        else:
            files_proc.append(path_img)
    n_imgs = len(files_proc)

    if n_imgs == 0:
        log_message(f'NO IMAGES FOUND. Check your settings.', callback_fun=callback_log)
        return

    # Process files

    for idx, path_img in enumerate(files_proc):
        imgs = []
        files = []
        sizes_orginal = []

        log_message(f'Segmenting image : {path_img.name}', callback_fun=callback_log)

        if callback_status:
            callback_status(f'Segmenting image : {path_img.name}')

        if callback_progress:
            progress = float((idx+1)/n_imgs)
            callback_progress(progress)

        # Read images
        img = imread(str(path_img))
        sizes_orginal.append(img.shape)

        # Resize
        if new_size:
            img = resize(img, new_size)

        img_zeros = np.zeros(img.shape)

        # For object segmentation
        img_3d_dpi = np.dstack([img_zeros, img_zeros, img])
        imgs.append(img_3d_dpi)
        files.append(path_img)

        # >>> Call function for prediction
        data = {'imgs': imgs,
                'file_names': files,
                'sizes_orginal': sizes_orginal,
                'channels': channels,
                'new_size': new_size,
                'obj_name': obj_name}

        # Create new output path if specified
        if not isinstance(path_save, pathlib.PurePath):
            path_save_results = create_output_path(path_img.parent, path_save_str_replace, subfolder='', create_path=True)
            path_save_settings = path_save_results

        cellpose_predict(data, config, path_save=path_save_results, callback_log=callback_log)

    log_message(f'\n BATCH SEGMENTATION finished', callback_fun=callback_log)
    #return {'status': 'segmentation finished'}


# Function to load and segment nuclei images individually 
def segment_cells_nuclei_indiv(path_scan, strings, img_ext, new_size, sizes, models, path_save, input_subfolder=None, callback_log=None, callback_status=None, callback_progress=None): 
    """[summary] segment cells and nuclei in bulk, e.g. first all images are loaded and then segmented. 
    TODO: specify parameters
    Parameters
    ----------
    path_scan : [type]
        [description]
    strings : [type]
        [description]
    img_ext : [type]
        [description]
    new_size : [type]
        [description]
    sizes : [type]
        [description]
    models : [type]
        [description]
    path_save : pathlin object or string
        Path to save results,
        - If Pathlib object, then this absolute path is used.
        - If 'string' a replacement operation on the provided name of the data path will be applied (see create_output_path).
          And results will be stored in subfolder 'segmentation-input'
    callback_log : [type], optional
        [description], by default None
    callback_status : [type], optional
        [description], by default None
    callback_progress : [type], optional
        [description], by default None
    """

    # Print all input parameters
    log_message(f"Function (segment_cells_nuclei_indiv) called with: {str(locals())} ", callback_fun=callback_log) 

    # Get parameters
    (str_cyto, str_nuclei) = strings
    (size_cells, size_nuclei) = sizes
    (model_cells, model_nuclei) = models

    # Use provided absolute user-path to save images.
    if isinstance(path_save, pathlib.PurePath):
        path_save_results = path_save
        if not path_save_results.is_dir():
            path_save_results.mkdir(parents=True)

    else:
        path_save_str_replace = path_save

    # Configurations
    device = check_device(callback_log=callback_log)

    config_nuclei = {'model_type': model_nuclei, 
                     'obj_size': size_nuclei,
                     'device': device}

    config_cyto = {'model_type': model_cells, 
                   'obj_size': size_cells,
                   'device': device}

    channels_cyto = [1, 3]
    channels_nuclei = [0, 1]

    # Loop over data
    log_message(f'\nLoading image pairs and segment them on the fly', callback_fun=callback_log) 

    if not path_scan.is_dir():
        log_message(f'Path {path_scan} does not exist.', callback_fun=callback_log) 
        return

    # Search for file to be analyzed
    log_message(f'\nLoading images and segment them on the fly', callback_fun=callback_log)
    files_proc = []
    for path_img in path_scan.rglob(f'*{str_cyto}*{img_ext}'):
        if input_subfolder:
            if path_img.parts[-2] == input_subfolder:
                files_proc.append(path_img)
        else:
            files_proc.append(path_img)
    n_imgs = len(files_proc)

    if n_imgs == 0:
        log_message(f'NO IMAGES FOUND. Check your settings.', callback_fun=callback_log)
        return

    # Process files

    for idx, path_cyto in enumerate(files_proc):
        imgs_cyto = []
        imgs_nuclei = []
        files_cyto = []
        files_nuclei = []
        sizes_orginal = []        

        log_message(f'Segmenting image : {path_cyto.name}', callback_fun=callback_log)

        if callback_status:
            callback_status(f'Segmenting image : {path_cyto.name}')

        if callback_progress:
            progress = float((idx+1)/n_imgs)
            callback_progress(progress)

        # DAPI image: existing?
        path_nuclei = Path(str(path_cyto).replace(str_cyto, str_nuclei))
        if not path_nuclei.is_file():
            log_message(f'DAPI image not found : {path_nuclei}', callback_fun=callback_log)
            continue

        # Read images
        img_cyto = imread(str(path_cyto))
        img_nuclei = imread(str(path_nuclei))
        sizes_orginal.append(img_cyto.shape)

        # Resize
        if new_size:
            img_cyto = resize(img_cyto, new_size)
            img_nuclei = resize(img_nuclei, new_size)

        img_zeros = np.zeros(img_cyto.shape)

        # For cell segmentation
        img_3d = np.dstack([img_cyto, img_zeros, img_nuclei])
        imgs_cyto.append(img_3d)
        files_cyto.append(path_cyto)

        # For nuclei segmentation
        img_3d_dpi = np.dstack([img_zeros, img_zeros, img_nuclei])
        imgs_nuclei.append(img_3d_dpi)
        files_nuclei.append(path_nuclei)

        # Create new output path if specified
        if not isinstance(path_save, pathlib.PurePath):
            path_save_results = create_output_path(path_cyto.parent, path_save_str_replace, subfolder='', create_path=True)
            path_save_settings = path_save_results

        # >>> Call function for prediction of cell
        data_cyto = {'imgs': imgs_cyto,
                     'file_names': files_cyto,
                     'sizes_orginal': sizes_orginal,
                     'channels': channels_cyto,
                     'new_size': new_size,
                     'obj_name': 'cells'}

        cellpose_predict(data_cyto, config_cyto, path_save=path_save_results, callback_log=callback_log)

        # >>> Call function for prediction of nuclei
        data_nuclei = {'imgs': imgs_nuclei,
                       'file_names': files_nuclei,
                       'sizes_orginal': sizes_orginal,
                       'channels': channels_nuclei,
                       'new_size': new_size,
                       'obj_name': 'nuclei'}

        cellpose_predict(data_nuclei, config_nuclei, path_save=path_save_results, callback_log=callback_log)

    log_message(f'\n BATCH SEGMENTATION finished', callback_fun=callback_log)
    #return {'status': 'segmentation finished'}




# >>>> OLDER IMPLEMENTATIONS .... the ones above have the advantage that outputs are immediately generate.


# Function to load and segment nuclei images
def segment_cells_nuclei(path_scan, strings, img_ext, new_size, sizes, models, path_save, callback_log=None): 
    """ TODO: segment cells and nuclei in bulk, e.g. first all images are loaded and then segmented. 

    Parameters
    ----------
    path_scan : [type]
        [description]
    strings : [type]
        [description]
    img_ext : [type]
        [description]
    new_size : [type]
        [description]
    sizes : [type]
        [description]
    models : [type]
        [description]
    path_save : [type]
        [description]
    """

    # Print all input parameters
    print("Function (segment_cells_nuclei) called with: ", locals())

    # Get parameters
    (str_cyto, str_nuclei) = strings
    (size_cells, size_nuclei) = sizes
    (model_cells, model_nuclei) = models

    # Which device to use
    device = check_device(callback_log=callback_log)

    # Load data
    imgs_cyto, imgs_nuclei, files_cyto, files_nuclei, channels_cyto, channels_nuclei, sizes_orginal = load_imgs_ctyo_nuclei(
                                                            path_scan=path_scan, 
                                                            str_cyto=str_cyto,     
                                                            str_nuclei=str_nuclei,
                                                            img_ext=img_ext, 
                                                            new_size=new_size,
                                                            callback_log=callback_log)

    # >>> Call function for prediction of cell
    config = {'model_type': model_cells, 
              'obj_size': size_cells,
              'device': device}

    data = {'imgs': imgs_cyto,
            'file_names': files_cyto, 
            'sizes_orginal': sizes_orginal,
            'channels': channels_cyto,
            'new_size': new_size,
            'obj_name': 'cells'}

    cellpose_predict(data, config, path_save=path_save, callback_log=callback_log)

    # >>> Call function for prediction of nuclei
    config = {'model_type': model_nuclei, 
              'obj_size': size_nuclei,
              'device': device}

    data = {'imgs': imgs_nuclei,
            'file_names': files_nuclei, 
            'sizes_orginal': sizes_orginal,
            'channels': channels_nuclei,
            'new_size': new_size,
            'obj_name': 'nuclei'}

    cellpose_predict(data, config, path_save=path_save, callback_log=callback_log)

# Function to load and segment nuclei images
def segment_nuclei(path_scan, str_dapi, img_ext, new_size, size_nuclei, model, path_save,callback_log=None):
    """ Wrapper function to load and segment nuclei in 2D images. 

    Parameters
    ----------
    path_scan : pathline Path object
        Folder to scan for images that will be segmented.
    str_dapi : str
        String that has be contained in the file-name in order to be added to loaded.
    img_ext : str
        Image file extension. 
    new_size : tuple
        New size of image if image should be resized. Empty tuple for no resizing. 
    size_nuclei : int
        Typical diameter of nuclei in image
    model : str
        CellPose model that should be used for segmentation ('cyto' or 'nuclei').
        The cytoplasmic model works also well for nuclei, especially in densly 
        packed regions. 
    """
    
    # Print all input parameters
    print("Function (segment_cells_nuclei) called with: ", locals())
    
    # Which device to use
    device = check_device()
    
    # Load data
    imgs, files, channels, sizes_orginal = load_imgs_nuclei(path_scan=path_scan, 
                                                            str_dapi=str_dapi,
                                                            img_ext=img_ext, 
                                                            new_size=new_size)

    # Call function for prediction
    config = {'model_type': model, 
            'obj_size': size_nuclei,
            'device': device}

    data = { 'imgs': imgs,
            'file_names': files, 
            'sizes_orginal': sizes_orginal,
            'channels': channels,
            'new_size': new_size,
            'obj_name':'nuclei'
    }
                
    cellpose_predict(data, config, 
                    path_save = path_save )



def load_imgs_nuclei(path_scan, str_dapi, img_ext, new_size, callback_log=None):
    """[summary]
    
    Parameters
    ----------
    path_scan : pathline Path object
        Folder to scan for images that will be segmented.
    str_dapi : str
        String that has be contained in the file-name in order to be added to loaded.
    img_ext : str
        Image file extension. 
    new_size : tuple
        New size of image if image should be resized. Empty tuple for no resizing. 
    
    Returns
    -------
    [type]
        [description]
    """
    # Create processing lists
    channels_nuclei = [0, 1]
    imgs_nuclei = []
    files_nuclei = []
    sizes_orginal = []
    log_message(f'Loading images and creating processing list', callback_fun=callback_log)    

    for path_dapi in path_scan.glob(f'*{str_dapi}*{img_ext}'):

        # Load image and resize if specified
        img_dapi = imread(str(path_dapi))
        sizes_orginal.append(img_dapi.shape)
        
        if new_size:
            img_dapi = resize(img_dapi, new_size)
        img_zeros = np.zeros(img_dapi.shape)

        # For nuclei segmentation
        img_3d_dpi = np.dstack([img_zeros, img_zeros, img_dapi])
        imgs_nuclei.append(img_3d_dpi)
        files_nuclei.append(path_dapi)
        
    log_message(f' ... prepared {len(imgs_nuclei)} images for segmentation ...\n', callback_fun=callback_log) 

    return imgs_nuclei, files_nuclei, channels_nuclei, sizes_orginal


# Load data for nuclei and cyto segmentation
def load_imgs_ctyo_nuclei(path_scan, str_cyto, str_nuclei, img_ext, new_size, callback_log=None ):
    """[summary]
    
    Parameters
    ----------

    path_scan : pathline Path object
        Folder to scan for images that will be segmented.
    str_cyto : str
        String that has be contained in the file-name in order to be added to loaded.
    str_nuclei : str
        String that has be contained in the file-name in order to be added to loaded.
    img_ext : str
        Image file extension. 
    new_size : tuple
        New size of image if image should be resized. Empty tuple for no resizing. 
        
    Returns
    -------
    [type]
        [description]
    """
    imgs_cyto = []
    imgs_nuclei = []
    files_cyto = []
    files_nuclei = []
    sizes_orginal = []
    log_message(f'Loading images and creating processing list', callback_fun=callback_log) 
               
    # Create processing lists
    channels_cyto = [1, 3]
    channels_nuclei = [0, 1]
    
    if not path_scan.is_dir():
        log_message(f'Path {path_scan} does not exist.', callback_fun=callback_log) 
        return

    for path_cyto in path_scan.glob(f'*{str_cyto}*{img_ext}'):
        # DAPI image: existing?
        path_nuclei = Path(str(path_cyto).replace(str_cyto, str_nuclei))
        if not path_nuclei.is_file():
            log_message(f'DAPI image not found : {path_nuclei}', callback_fun=callback_log)
            continue

        # Read images
        img_cyto = imread(str(path_cyto))
        img_nuclei = imread(str(path_nuclei))
        sizes_orginal.append(img_cyto.shape)

        # Resize
        if new_size:
            img_cyto = resize(img_cyto, new_size)
            img_nuclei = resize(img_nuclei, new_size)

        img_zeros = np.zeros(img_cyto.shape)

        # For cell segmentation
        img_3d = np.dstack([img_cyto, img_zeros, img_nuclei])
        imgs_cyto.append(img_3d)
        files_cyto.append(path_cyto)

        # For nuclei segmentation
        img_3d_dpi = np.dstack([img_zeros, img_zeros, img_nuclei])
        imgs_nuclei.append(img_3d_dpi)
        files_nuclei.append(path_nuclei)

    log_message(f' ... prepared {len(imgs_nuclei)} images for segmentation ...\n', callback_fun=callback_log)
    
    return  imgs_cyto, imgs_nuclei, files_cyto, files_nuclei, channels_cyto, channels_nuclei, sizes_orginal


def resize_mask(mask_small, size_orginal):
    """ Resize a label image.

    Parameters
    ----------
    mask_small : [type]
        [description]
    size_orginal : [type]
        [description]

    Returns
    -------
    [type]
        [description]
    """

    mask_full = np.zeros(size_orginal).astype('uint16')
    maski_template = np.zeros(mask_small.shape).astype('uint8')

    ind_objs = np.unique(mask_small)
    ind_objs = np.delete(ind_objs, np.where(ind_objs == 0))

    if ind_objs.size > 0:

        for obj_int in np.nditer(ind_objs):

            # Create binary mask for current object and find contour
            img_obj_loop = np.copy(maski_template)
            img_obj_loop[mask_small == obj_int] = 1

            img_obj_loop_large = resize(img_obj_loop, size_orginal, order=1).astype('bool')
            mask_full[img_obj_loop_large] = obj_int

    return mask_full