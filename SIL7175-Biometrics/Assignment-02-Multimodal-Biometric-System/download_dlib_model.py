import os, bz2, urllib.request

def main():
    os.makedirs('resources', exist_ok=True)
    url = 'http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2'
    bz2_path = 'resources/shape_predictor_68_face_landmarks.dat.bz2'
    dat_path = 'resources/shape_predictor_68_face_landmarks.dat'
    
    # Download
    print('Downloading dlib shape predictor (approx 61MB). This may take a minute...')
    urllib.request.urlretrieve(url, bz2_path)
    
    # Extract
    print('Extracting...')
    with open(dat_path, 'wb') as new_file, bz2.BZ2File(bz2_path, 'rb') as file:
        for data in iter(lambda : file.read(100 * 1024), b''):
            new_file.write(data)
            
    # Cleanup
    os.remove(bz2_path)
    print('Done! The dlib landmark predictor is ready in the resources folder.')

if __name__ == '__main__':
    main()
