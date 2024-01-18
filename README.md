# Custom Bible translations in ProPresenter 7

ProPresenter offers a list of bible translations to use during your services. In Dutch however quite a few translations are missing `NBV21` being one of them. After multiple requests to RenewedVision team to add it, they never did. After inspecting the code and file structure of how ProPresenter stores bibles on the disk I leveraged this to create new translations to the existing library.

## Prerequisites
- Python knowledge
- Knowledge on APIs and HTTP requests
- XML knowledge
- ProPresenter on a Windows machine

## How to

1. Observe that ProPresenter stores the Bibles on the location `%programdata%\RenewedVision\ProPresenter\Bibles`, each bible will be stored in a separate folder with a UUID as name. The folders itself have the following strucure:
```
│   BibleData.proPref
│
├───818d0d02-fa1e-4038-85f9-bb5fcc65497b
│   │   metadata.xml
│   │   rvmetadata.xml
│   │
│   ├───SearchIndex
│   │       segments.gen
│   │       segments_2
│   │       version
│   │       _0.cfs
│   │       _0.cfx
│   │
│   └───USX_1
│           1CH.usx
│           1CO.usx
```
- `BibleData.proPref` - File containing the installed bibles on the machine
  - `{UUID}/metadata.xml` - Holds the [DBL metadata](https://thedigitalbiblelibrary.org/2017/07/07/introducing-dbl-metadata-2-0/) configuration
  - `{UUID}/rvmetadata.xml` - RenewedVision ProPresenter metadata that is used in the Bibles tab
  - `{UUID}/SearchIndex` - Folder containing the [Lucene search index](https://lucene.apache.org/) which is the generated index for the bible
  - `{UUID}/USX` - Folder containing the [USX XML files](https://ubsicap.github.io/usx/) per chapter

2. Run the Python script `retrieve_chapters_nbv21.py`.
<br>This will retrieve NBV21 bible chapter by chapter from the website and stores it in JSON format.
    ```shell
    python retrieve_chapters_nbv21.py
    ```

3. Run the script `json_to_usx.py`
   <br>This will convert the JSON contents to a valid USX book file by merging the different chapter files.
   ```shell
   python json_to_usx.py
   ```

4. Download the `005eb691-c7b9-4f87-84dc-e6afb79e77c5` folder from `/Resources` in this repository and place it in the the bible directory on you disk

5. Place the USX files that were generated in the folder `005eb691-c7b9-4f87-84dc-e6afb79e77c5/USX`

6. Reopen ProPresenter

## How does this work
Since USX is a common format for scriptures it possible to edit or change the contents of these files. ProPresenter only recognized known UUIDs, defining a new folder or modifing an existing one will therefore not work. It will match on the UUID (the folder name) and the bible translation abbreviation. With this we are essentially overwriting an other translation and using their identifiers. To make sure that ProPresenter will show the correct abbreviation and title we edit the metadata files.

As `NBV21` bible is licenced I am unable to give you its contents.