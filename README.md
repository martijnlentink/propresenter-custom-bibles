# Custom Bible translations in ProPresenter 7

![Custom translation in ProPresenter](/Resources/example.png)

ProPresenter offers a list of bible translations to use during your services. In Dutch however quite a few translations are missing `NBV21` being one of them. After multiple requests to RenewedVision team to add it, they never did. After inspecting the code and file structure of how ProPresenter stores bibles on the disk I leveraged this to create new translations which can be opened an used.

## Prerequisites
- Python knowledge
- Knowledge on APIs and HTTP requests
- XML knowledge
- ProPresenter

## How to

### Windows

1. Observe that ProPresenter stores the Bibles on the location `C:\RenewedVision\ProPresenter\Bibles`, each bible will be stored in a separate folder with a UUID as name.

2. Run the Python script `retrieve_chapters_nbv21.py`.
<br>This will retrieve NBV21 bible chapter by chapter from the website and stores it in JSON format.
    ```shell
    python retrieve_chapters_nbv21.py
    ```

1. Run the script `json_to_usx.py`
   <br>This will convert the JSON contents to a valid USX book file by merging the different chapter files.
   ```shell
   python json_to_usx.py
   ```

2. Download the `005eb691-c7b9-4f87-84dc-e6afb79e77c5` folder from `/Resources` in this repository and place it in the the bible directory on you disk

3. Place the USX files that were generated in the folder `005eb691-c7b9-4f87-84dc-e6afb79e77c5/USX`

4. Update `BibleData.proPref` file such that it contains an entry for our new translation (By using the translation definition of WARMB).

    <pre>InstalledBiblesNew=["6fb4fb55-78a4-43bc-ac6a-076818c7abfc|BB|BasisBijbel|1",<b>"005eb691-c7b9-4f87-84dc-e6afb79e77c5|WARMB|Nieuwe Bijbelvertaling 2021|1"</b>];</pre>

5. Reopen ProPresenter

### Mac

1. Observe that ProPresenter stores the Bibles on the location `/Library/Application Support/RenewedVision/RVBibles/v2/`, each bible will be stored in a ZIP file with extension `.rvbible`.

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

6. Zip the contents of the folder and place it in the directory where the other `.rvbible` files are. Finally rename it such that it has the extension `.rvbible` instead of zip,

7. ProPresenter for Mac should continuously detect new bibles. If this is not the case you can try to restart ProPresenter. Note that incorrect files might cause crashes!

## How does this work
ProPresenter enables you to install bibles through their in application store. This store contains many translations of scriptures in various languages, but since it is a closed store managed completely by RenewedVision only translations they add to their store themselves can be bought, installed and used.

After downloading a bible it is stored on the users machine for easy lookup and (offline) use. Installed bibles on a machine are available for all users and is not bound to a single user profile.
There is a slight difference in how these bibles are stored between Mac OSX systems and Windows.

On Windows these are stored in a Bibles folder, with an index file `BibleData.proRef`. This file holds a list of pipe separated bible installations with UUIDs refering to folder names where the contents of the translations are stored.

On Mac the contents of the bibles, which are the files in the UUID folders, are stored in a ZIP file with `.rvbible` as extension. For Mac there is no index file.

ProPresenter uses bibles stored in the [Unified Scripture XML](https://ubsicap.github.io/usx/) format. This is an open, common format and therefore modifying or extension is possible as there is plenty documentation on this. And with that, it opens up the opportunity for us to sideload different bible translations.

### Notes

- As I did research on how to approach this; to be able to sideload a scripture it is required that the abbreviation is known within ProPresenter. At various points inside the code a translation is identified by its translation, for that reason I am using an abbrevation of a translation and language that I'm not going to be using. In my case this was the `WARMB` translation.
- ProPresenter reads the `rvmetadata.xml` as reference on how to display the bible. That means that the name, abbrevation (through `displayAbbreviation`) can be overwritten. With that the bible translation you load into the system will behave exactly as a normal translation, but under the hood its original abbreviation is used to refer to it.
- On Windows it looks like that, just as the abbreviation, the UUID of a translation also needs to match up with an existing translation.
- On Mac XML comments in the `metadata.xml` will cause exceptions and ProPresenter to crash.
- When the bible translations on Windows are corrupt they will simply not appear in the dropdown. On Mac it will cause crashes.
- As `NBV21` bible is licenced, like most bibles, I am unable to give you its contents.

## Folder structure
ProPresenter stores the Bibles on the Windows location `%programdata%\RenewedVision\ProPresenter\Bibles`, each bible will be stored in a separate folder with a UUID as name. On Mac OSX this is `/Library/Application Support/RenewedVision/RVBibles/v2/`, each bible will be stored in a ZIP file with extension `.rvbible`.

```
│   BibleData.proPref
│
├───818d0d02-fa1e-4038-85f9-bb5fcc65497b | kjv-en.rvbible
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