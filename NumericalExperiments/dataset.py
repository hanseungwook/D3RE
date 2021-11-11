import numpy as np
import urllib.request
import os
import tarfile
import pickle
from sklearn.datasets import fetch_openml
from scipy.stats import multivariate_normal
from scipy.linalg import block_diag

def get_mnist():
    mnist = fetch_openml('mnist_784', data_home=".")

    x = mnist.data
    y = mnist.target
    # reshape to (#data, #channel, width, height)
    x = np.reshape(x, (x.shape[0], 1, 28, 28)) / 255.
    x_tr = np.asarray(x[:60000], dtype=np.float32)
    y_tr = np.asarray(y[:60000], dtype=np.int32)
    x_te = np.asarray(x[60000:], dtype=np.float32)
    y_te = np.asarray(y[60000:], dtype=np.int32)
    return (x_tr, y_tr), (x_te, y_te)


def binarize_mnist_class(y_train, y_test):
    y_train_bin = np.ones(len(y_train), dtype=np.int32)
    y_train_bin[y_train % 2 == 1] = -1
    y_test_bin = np.ones(len(y_test), dtype=np.int32)
    y_test_bin[y_test % 2 == 1] = -1
    return y_train_bin, y_test_bin


def unpickle(file):
    fo = open(file, 'rb')
    dictionary = pickle.load(fo, encoding='latin1')
    fo.close()
    return dictionary


def conv_data2image(data):
    return np.rollaxis(data.reshape((3, 32, 32)), 0, 3)


def get_cifar10(path="./mldata"):
    if not os.path.isdir(path):
        os.mkdir(path)
    url = "http://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"
    file_name = os.path.basename(url)
    full_path = os.path.join(path, file_name)
    folder = os.path.join(path, "cifar-10-batches-py")
    # if cifar-10-batches-py folder doesn't exists, download from website
    if not os.path.isdir(folder):
        print("download the dataset from {} to {}".format(url, path))
        urllib.request.urlretrieve(url, full_path)
        with tarfile.open(full_path) as f:
            f.extractall(path=path)
        urllib.request.urlcleanup()

    x_tr = np.empty((0, 32 * 32 * 3))
    y_tr = np.empty(1)
    for i in range(1, 6):
        fname = os.path.join(folder, "%s%d" % ("data_batch_", i))
        data_dict = unpickle(fname)
        if i == 1:
            x_tr = data_dict['data']
            y_tr = data_dict['labels']
        else:
            x_tr = np.vstack((x_tr, data_dict['data']))
            y_tr = np.hstack((y_tr, data_dict['labels']))

    data_dict = unpickle(os.path.join(folder, 'test_batch'))
    x_te = data_dict['data']
    y_te = np.array(data_dict['labels'])

    bm = unpickle(os.path.join(folder, 'batches.meta'))
    # label_names = bm['label_names']
    # rehape to (#data, #channel, width, height)
    x_tr = np.reshape(x_tr, (np.shape(x_tr)[0], 3, 32, 32)).astype(np.float32)
    x_te = np.reshape(x_te, (np.shape(x_te)[0], 3, 32, 32)).astype(np.float32)
    # normalize
    x_tr /= 255.
    x_te /= 255.
    return (x_tr, y_tr), (x_te, y_te)  # , label_names


def binarize_cifar10_class(y_train, y_test):
    y_train_bin = np.ones(len(y_train), dtype=np.int32)
    y_train_bin[(y_train == 2) | (y_train == 3) | (y_train == 4) | (y_train == 5) | (y_train == 6) | (y_train == 7)] = -1
    y_test_bin = np.ones(len(y_test), dtype=np.int32)
    y_test_bin[(y_test == 2) | (y_test == 3) | (y_test == 4) | (y_test == 5) | (y_test == 6) | (y_test == 7)] = -1
    return y_train_bin, y_test_bin


def make_dataset(dataset, n_labeled, n_unlabeled):
    def make_pu_dataset_from_binary_dataset(x, y, labeled=n_labeled, unlabeled=n_unlabeled):
        labels = np.unique(y)
        positive, negative = labels[1], labels[0]
        x, y = np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.int32)
        assert(len(x) == len(y))
        perm = np.random.permutation(len(y))
        x, y = x[perm], y[perm]
        n_p = (y == positive).sum()
        n_lp = labeled
        n_n = (y == negative).sum()
        n_u = unlabeled
        if labeled + unlabeled == len(x):
            n_up = n_p - n_lp
        elif unlabeled == len(x):
            n_up = n_p
        else:
            raise ValueError("Only support |P|+|U|=|X| or |U|=|X|.")
        _prior = float(n_up) / float(n_u)
        xlp = x[y == positive][:n_lp]
        xup = np.concatenate((x[y == positive][n_lp:], xlp), axis=0)[:n_up]
        xun = x[y == negative]
        x = np.asarray(np.concatenate((xlp, xup, xun), axis=0), dtype=np.float32)
        print(x.shape)
        y = np.asarray(np.concatenate((np.ones(n_lp), -np.ones(n_u))), dtype=np.int32)
        perm = np.random.permutation(len(y))
        x, y = x[perm], y[perm]
        return x, y, _prior

    def make_pn_dataset_from_binary_dataset(x, y):
        labels = np.unique(y)
        positive, negative = labels[1], labels[0]
        X, Y = np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.int32)
        n_p = (Y == positive).sum()
        n_n = (Y == negative).sum()
        Xp = X[Y == positive][:n_p]
        Xn = X[Y == negative][:n_n]
        X = np.asarray(np.concatenate((Xp, Xn)), dtype=np.float32)
        Y = np.asarray(np.concatenate((np.ones(n_p), -np.ones(n_n))), dtype=np.int32)
        perm = np.random.permutation(len(Y))
        X, Y = X[perm], Y[perm]
        return X, Y

    (x_train, y_train), (x_test, y_test) = dataset
    x_train, y_train, prior = make_pu_dataset_from_binary_dataset(x_train, y_train)
    x_test, y_test = make_pn_dataset_from_binary_dataset(x_test, y_test)
    print("training:{}".format(x_train.shape))
    print("test:{}".format(x_test.shape))
    return list(zip(x_train, y_train)), list(zip(x_test, y_test)), prior


def load_dataset(dataset_name):
    if dataset_name == "mnist":
        (trainX, trainY), (testX, testY) = get_mnist()
        trainY, testY = binarize_mnist_class(trainY, testY)
    elif dataset_name == "cifar10":
        (trainX, trainY), (testX, testY) = get_cifar10()
        trainY, testY = binarize_cifar10_class(trainY, testY)
    elif dataset_name == "synthetic":
        mu_p, mu_q, scale_p, scale_q = create_syndata_params(means=[-1, 1], dim=40, mi=100)
        p_dist = multivariate_normal(mean=mu_p, cov=scale_p)
        q_dist = multivariate_normal(mean=mu_q, cov=scale_q)

        p_samples_train = p_dist.rvs(size=100000)
        q_samples_train = q_dist.rvs(size=100000)

        p_samples_test = p_dist.rvs(size=500)

        ones = np.ones(10000)
        zeros = np.zeros(10000)

        trainX = np.concatenate((p_samples_train, q_samples_train), axis=0)
        trainY = np.concatenate((ones, zeros), axis=0)

        # Only p samples in test dataset
        testX = p_samples_test
        testY = np.copy(ones)
        
    else:
        raise ValueError("dataset name {} is unknown.".format(dataset_name))

    #trainX = np.transpose(trainX, (0, 2, 3, 1))
    #testX = np.transpose(testX, (0, 2, 3, 1))
    #print(trainX.shape)
    #print(testX.shape)
    return trainX, trainY, testX, testY

def create_syndata_params(means=[-1, 1], dim=40, mi=100):
    mu_1=means[0]+np.zeros((dim), dtype="float32")
    mu_2=means[1]+np.zeros((dim), dtype="float32")

    rho = get_rho_from_mi(mi, dim)  # correlation coefficient

    scale_p = block_diag(*[[[1, rho], [rho, 1]] for _ in range(dim // 2)])
    scale_p = np.float32(scale_p)
    scale_q = np.ones(dim, dtype="float32")

    return mu_1, mu_2, scale_p, scale_q

def get_rho_from_mi(mi, n_dims):
    """Get correlation coefficient from true mutual information"""
    x = (4 * mi) / n_dims
    return (1 - np.exp(-x)) ** 0.5  # correlation coefficient
