""" Dataset Loaders

Set of functions to use to load the ADNI dataset.

"""
import os
import re
import platform
import torch
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import train_test_split
from PIL import Image

# Helper function to extract patient ID from the filename
def extract_patient_id(file_name):
    return re.match(r"([^_]+)_", file_name).group(1)

class ADNIDataset(Dataset):
    def __init__(self, image_paths, labels, transform=None):
        """
        Custom Dataset for loading ADNI data with labels.
        
        Args:
            image_paths (list): List of image file paths.
            labels (list): List of corresponding labels (0 for NC, 1 for AD).
            transform (torchvision.transforms): Image transformations.
        """
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path)
        label = self.labels[idx]

        if self.transform:
            image = self.transform(image)

        return image, label
    
# Custom Transform to add Gaussian Noise
class AddGaussianNoise(object):
    def __init__(self, mean=0.0, std=1.0):
        self.mean = mean
        self.std = std

    def __call__(self, tensor):
        noise = torch.randn(tensor.size()) * self.std + self.mean
        noisy_tensor = tensor + noise
        # Clip the tensor to ensure values remain in [0, 1] range
        return torch.clamp(noisy_tensor, 0., 1.)

    def __repr__(self):
        return f"{self.__class__.__name__}(mean={self.mean}, std={self.std})"
    

def load_adni_data(root_dir, valid_size=0.2, batch_size=32, testing=False):
    """
    Load the ADNI dataset and ensure no leakage by splitting data subject-wise.
    
    Args:
        root_dir (str): Root directory containing the 'train' folder with NC and AD subfolders.
        valid_size (float): Fraction of the training set to be used for validation.
        batch_size (int): Batch size for DataLoader.
        
    Returns:
        train_loader (DataLoader): DataLoader for training set.
        val_loader (DataLoader): DataLoader for validation set.
    """
    # Initialize lists for storing image paths and labels
    image_paths = []
    labels = []

    directory = 'train' if not testing else 'test'

    # Load images from NC (Normal Control) and AD (Alzheimer's Disease) folders
    classes = {'NC': 0, 'AD': 1}  # 0 for NC, 1 for AD
    for class_name, label in classes.items():
        class_dir = os.path.join(root_dir, directory, class_name)
        for file_name in os.listdir(class_dir):
            if file_name.endswith(('.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(class_dir, file_name))
                labels.append(label)

    if not testing:  # If not testing, need to split into training and validation set

        # Extract patient IDs to ensure no leakage
        patient_ids = [extract_patient_id(os.path.basename(path)) for path in image_paths]
        
        # Create a DataFrame to assist in patient-wise splitting
        data = list(zip(image_paths, labels, patient_ids))
        
        # Perform a patient-wise split
        unique_patients = set(patient_ids)
        train_patients, val_patients = train_test_split(list(unique_patients), test_size=valid_size, random_state=42)
        
        # Split the dataset into training and validation based on patient IDs
        train_data = [(img, lbl) for img, lbl, pid in data if pid in train_patients]
        val_data = [(img, lbl) for img, lbl, pid in data if pid in val_patients]

        # Separate image paths and labels
        train_image_paths, train_labels = zip(*train_data)
        val_image_paths, val_labels = zip(*val_data)

    mean = 0.1156
    std = 0.2199
    # Define image transformations
    # ! Check the correct transforms are used
    if not testing:
        transform = transforms.Compose([
            transforms.CenterCrop((224, 224)),  # Resize to fit model input size (256 x 240)
            transforms.RandomVerticalFlip(p=0.5),
            transforms.ToTensor(),  # Convert image to PyTorch tensor
            transforms.Normalize(mean=[mean], std=[std]) 
        ])

    else:  # Testing
        transform = transforms.Compose([
        transforms.CenterCrop((224, 224)),  # Resize to fit model input size (256 x 240)
        transforms.ToTensor(),  # Convert image to PyTorch tensor
        transforms.Normalize(mean=[mean], std=[std]) 
    ])

    if not testing:
        # Create ADNIDataset instances for training and validation
        train_dataset = ADNIDataset(train_image_paths, train_labels, transform=transform)
        val_dataset = ADNIDataset(val_image_paths, val_labels, transform=transform)
    else:
        train_dataset = ADNIDataset(image_paths, labels, transform=transform)

    # Create DataLoaders for batching and parallel data loading
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=1)

    if not testing:
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=1)
        return train_loader, val_loader

    return train_loader  # No validation

#if platform.system() == "Windows":
#    root_dir = 'ADNI_AD_NC_2D/AD_NC'
#else:
#    root_dir = '~/ADNI/AD_NC'

#train_loader, val_loader = load_adni_data(root_dir)