"""Source-linked GST rate suggestions for Vibe4You catalogue, effective Sep 2025.

Never commit recommendations to the GST classification registry automatically.
A name/category is often insufficient to establish legal HSN; apply narrow
rules, show source and decision status, and keep prices unchanged.
"""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any

GOODS_RATE_SOURCE = (
    "https://courier.cbic.gov.in/ECCS/advisory/2025/"
    "NOTIFICATION%20NO.%209_2025-INTEGRATED%20TAX%20(RATE)"
    "%20-1759486719.pdf"
)
RATE_EFFECTIVE_DATE = "2025-09-22"
THRESHOLD = Decimal("2500.00")

FOOTWEAR = re.compile(
    r"\b(?:shoes?|sneakers?|sandals?|slippers?|heels?|slides?|"
    r"boots?|loafers?|mules?|wedges?|flip[- ]flops?|clogs?|"
    r"ballerinas?|pumps?|chappals?)\b", re.IGNORECASE
)
APPAREL = re.compile(
    r"\b(?:t[- ]?shirts?|shirts?|jeans?|kurtas?|kurtis?|"
    r"trousers?|pants?|dresses?|leggings?|jackets?|"
    r"hoodies?|sweatshirts?|sweaters?|"
    r"track pants?|tops?|blouses?|tunics?)\b", re.IGNORECASE
)
CASIO = re.compile(
    r"\b(?:casio\s+)?(?:vintage\s+)?(?:f[- ]?91w|a158wa|"
    r"f[- ]?91wm|f[- ]?91ws)\b", re.IGNORECASE
)
NOT_WATCH = re.compile(
    r"\b(?:strap|band|replacement|battery|smartwatch|case\s+only|"
    r"watch\s+case|watch\s+protector|charger)\b", re.IGNORECASE
)

# V12 source: owner-declared PLASTIC material (no supplier proof) for
# 549 exact DIVNIX product ids in offline audited material declaration.
# HSN 3926 / GST 18% is a conditional tariff research CANDIDATE only.
# Do NOT auto-approve any tax records, change prices, or issue invoices.
DIVNIX_OWNER_PLASTIC_COVER_V12_IDS = frozenset({
    'shopprod_0000f5778c0eed44b53621bc',
    'shopprod_0057c89e8714a56de47542c3',
    'shopprod_00afb2d9856c5e4941151418',
    'shopprod_01994bfc07f083af5b924e84',
    'shopprod_0242fcbf988598c55f5e96fb',
    'shopprod_026cbc2424ae131828f9a9f8',
    'shopprod_029454ef4f98d3c6055abbc5',
    'shopprod_02c78e665eccc074b03e83d3',
    'shopprod_030f56535ef43e293768940a',
    'shopprod_03b7ec802c301cb05e702c8d',
    'shopprod_03cce665c5834a13db28ac56',
    'shopprod_05b445aba3daba52d4d3bf2b',
    'shopprod_0691ce3f19dd750365310952',
    'shopprod_06abb759c0ea53b92c73ae0b',
    'shopprod_0717e893be338c045f4c6ddb',
    'shopprod_07b352d8196f1602df4fa944',
    'shopprod_080ae2977e536aeb1657170f',
    'shopprod_08286848904701ebeeb6d874',
    'shopprod_08639d8fbc71dd7386c644de',
    'shopprod_09aba78f3d04ba0aeb94a186',
    'shopprod_0a3c8c89ca7b2c07ad1ad225',
    'shopprod_0b0e94f9fed5419a7aa5ce67',
    'shopprod_0b57920bb5edec24afb98391',
    'shopprod_0bf96833756b3e5ec08b7042',
    'shopprod_0c1da70182d295750b9e2fbe',
    'shopprod_0c3094704652020869092ae9',
    'shopprod_0c8461ccd82a6076db2c0d24',
    'shopprod_0d84b529f2a601e577ebe9fe',
    'shopprod_0e37831acb4a8419ab20d007',
    'shopprod_0eb41dc25a41421a0d74b353',
    'shopprod_10aab3519bf55c8aa129db84',
    'shopprod_10ffa55a56ba4f861bff727c',
    'shopprod_115addc49981e74b9c32944c',
    'shopprod_12426ebea9822b72d23a6a0d',
    'shopprod_12aaa16456e61da05c0502db',
    'shopprod_12fcc370f7f80e05a8be1b6d',
    'shopprod_1359a97be6ddb4c59d33b60e',
    'shopprod_140d63f358b2ce46c9a984ef',
    'shopprod_1588bbdfa861a823d9428457',
    'shopprod_15ce1504fb591c989d42fc93',
    'shopprod_16177a66cbba0da77da3584b',
    'shopprod_18835e74abc4b886b43f3e11',
    'shopprod_188f34b332be6b88e0433271',
    'shopprod_189ab8d910ee2d907773e50f',
    'shopprod_1a085f42927ba4f815a8f6fe',
    'shopprod_1a2d659ef4d9987d2690f56c',
    'shopprod_1a9b768015987f79681a2863',
    'shopprod_1aa3a11622551682c6a81232',
    'shopprod_1c00bb6794cefd0e43710c88',
    'shopprod_1c5980a68a9e66024f93219b',
    'shopprod_1c76981c04d25384387bce03',
    'shopprod_1d80d84c04d4c7f7badce3bd',
    'shopprod_1e7f08e5a2a73a383ff035cc',
    'shopprod_1f3c056be7fab32da25811a4',
    'shopprod_1f43238b61ebc224dfed8cf0',
    'shopprod_1fa27a8669e21eeb82a7d6fa',
    'shopprod_1fe012840aeeb713f1e9fc9b',
    'shopprod_20170dbc5d7200347acc5500',
    'shopprod_20e48d1516d72446bd5331f2',
    'shopprod_21cb501a74dfcf63cfb9bce4',
    'shopprod_21d63eac4a581367eee4a57c',
    'shopprod_21eb4e0b9614ac4c5a83161e',
    'shopprod_21f312a337f0b3e56a245e0d',
    'shopprod_234b2f65ca560a99f2444780',
    'shopprod_237e2ef6262dc9348b72edc5',
    'shopprod_2395d6fbf8c3d322e8f878d1',
    'shopprod_23adf4f9918babd45a8a4365',
    'shopprod_23f2f938866ddab9fffb9a55',
    'shopprod_241f2300529775a44d299f57',
    'shopprod_24801db5617ea23d9104d34d',
    'shopprod_24902b8057fe9a162b82b728',
    'shopprod_249a112f667a10e8cd1c8539',
    'shopprod_24e594af8caa779d95dbfb16',
    'shopprod_2537ef8245d01b901dc7482d',
    'shopprod_258cfb252b29093e299d40cd',
    'shopprod_273accff5262d29a872419de',
    'shopprod_27c0033e275785456d737b7a',
    'shopprod_27ccae5048565edfea2b4f99',
    'shopprod_2817c09ba0e9f7c933213a03',
    'shopprod_29d152d13fc30d9da794d968',
    'shopprod_29ea07324b262c5b97cf8c81',
    'shopprod_2a25e53b870a43fb6d002ed8',
    'shopprod_2a44e5217d53ab27fba8bee9',
    'shopprod_2a6bd8e5887f96a04142f1ed',
    'shopprod_2a8150e1f96936d100a53464',
    'shopprod_2aba34a2ae816500d1800420',
    'shopprod_2ac78b4de31b77b130f12744',
    'shopprod_2b70a8c050da5713bd505f98',
    'shopprod_2b7c8a1ed421078db4de0190',
    'shopprod_2bc3afcb0ead5e09d1cb75fd',
    'shopprod_2cac7ac66342b6becafc34e7',
    'shopprod_2d155ad39ed4cbd3f0e93322',
    'shopprod_2d2b6d284bd26ff15c153ed6',
    'shopprod_2d3681dba99b1dccbeb5c6f1',
    'shopprod_2d9515c88d96d6c17ea1a7d0',
    'shopprod_2dd0d2d746cceed499dd4d71',
    'shopprod_2ddd89855b5e018d031be984',
    'shopprod_2e1752f3af83cc5a30c0849d',
    'shopprod_2e1e39ad17788f83c475aec6',
    'shopprod_2e3d3a7d88628feec52eb0af',
    'shopprod_2e770eafdecab14c736b6eb3',
    'shopprod_2ebbc8b08384279d76011d74',
    'shopprod_30312d2cb1fc618574dd363b',
    'shopprod_307e8c178e77947b67229181',
    'shopprod_31669f7368710e45fb9e0365',
    'shopprod_318a6a9c8a120f6554412311',
    'shopprod_31dedf36b3ca6c32e34c20de',
    'shopprod_31f777834a0ba0349c0b50d5',
    'shopprod_32b58569bbc544e791a6708e',
    'shopprod_33296e6f2f545763a58f6ac3',
    'shopprod_33d77f306ccd4aeb1c0d1a63',
    'shopprod_33f878e67e335f65b1b44545',
    'shopprod_3490b414cc06e846775fc19a',
    'shopprod_34ece1d092b69d9daf4d00ca',
    'shopprod_34fe5ce4505bfb5b1d11eff1',
    'shopprod_356df2f85e163a5f34ede634',
    'shopprod_3573e0e22fcee6d76b218c07',
    'shopprod_35f22c9fae7dd60f6916eb7d',
    'shopprod_360b8aef425e3083e27dc76c',
    'shopprod_365c89732d5ac6211e37fb40',
    'shopprod_366bf41b268b9c15ea9b5fe0',
    'shopprod_36eb66ca2046f664ab205d48',
    'shopprod_371d0ed4d7664574eafe4212',
    'shopprod_37b1ca66927b6ea527a5281e',
    'shopprod_3894f12d71e31b26c4212652',
    'shopprod_38a7d9d2360b5e3c4362d06c',
    'shopprod_38cf2549c32dadaae3b8ddc1',
    'shopprod_394e95917e24bd0d37f121ad',
    'shopprod_3a96fec5401eabda02a9bc67',
    'shopprod_3b59dfe49ec7707f8d632dcb',
    'shopprod_3bc54fc212e5e310d9fcedc3',
    'shopprod_3bdf00a9b420c00653872ccf',
    'shopprod_3c397c4b1a72b3bfd0c2d5b9',
    'shopprod_3d69ef8d4a68162f1125a61e',
    'shopprod_3d71656fefaa781edaf2ebb3',
    'shopprod_3ddda550f4b61bfd8b3559cb',
    'shopprod_3e67343beeee31a8184848b4',
    'shopprod_3eb14b529e5b8f925dee2ae1',
    'shopprod_3ed36053598d16b0be12abca',
    'shopprod_3f1dc2cc697e03fcbc74cc37',
    'shopprod_3f477448000b64edbb9e4862',
    'shopprod_3fa8b2e338cbd1470c257686',
    'shopprod_3febdf66a449b5989192d99d',
    'shopprod_411aaa2335c55f56746b3472',
    'shopprod_414fb77bf09bd69e02f2894b',
    'shopprod_417aaaaa534cccf3a1b94d9e',
    'shopprod_447fe35e60ae29cea445d584',
    'shopprod_448114a849067f4c930311ee',
    'shopprod_4650229d9898fa61ac2dc0f3',
    'shopprod_472f8493d4a090727d74a1e1',
    'shopprod_47626d67efbaaafacb84a5a4',
    'shopprod_477d5c516b01337f7b9f9da6',
    'shopprod_47d8b76f6fbca47ab70ad7fa',
    'shopprod_48910d8b0c0d7c84690a1cc7',
    'shopprod_48c24e3e4b649e0819686250',
    'shopprod_48ebe94ad63efbabd1aaf01e',
    'shopprod_4903fb81a575e4b9f2408184',
    'shopprod_491b5ee85068fe62e3ac6283',
    'shopprod_49461c0e832f5779a2a3058b',
    'shopprod_49659096ad4bfd5517233a6d',
    'shopprod_4a3b0b0c6b3c36da37a46620',
    'shopprod_4a9812913680e366f9588849',
    'shopprod_4c7a32b3f1b2121766c0f2a8',
    'shopprod_4c8726568d130ec8d87dd633',
    'shopprod_4d2510122a2dd1751c830f50',
    'shopprod_4d9b6d11fb7944c22d5eefd7',
    'shopprod_4e016955801246852510dd98',
    'shopprod_4e67a49b89ce80bf4c3b7449',
    'shopprod_4ea12f0bcce3bf779b0cd5d5',
    'shopprod_4eb4a8ce84a9ca247256d138',
    'shopprod_4f10c6df154dca9024649265',
    'shopprod_4f42d6a8ba3edfbbf2d01298',
    'shopprod_50274d261f56348a217845e6',
    'shopprod_50493c2a91f7f3c2715ef922',
    'shopprod_50c3eef960747725b974c283',
    'shopprod_51ec427fcff09c89d263fbb6',
    'shopprod_52496d96da0c2277fe67b7f6',
    'shopprod_52f7a983fe83d5f6e88aebf5',
    'shopprod_531a33170429e44b16c2ed70',
    'shopprod_537def04630f38681bb4697d',
    'shopprod_53aace90c8db02415bfa097f',
    'shopprod_566713229f795ff161ad2a5a',
    'shopprod_57955057565703eda14a0c17',
    'shopprod_580a02a2afabd6a91d7bab76',
    'shopprod_583ce691051c7c59a20f5ff1',
    'shopprod_58c873b22c539592e83a4ef2',
    'shopprod_59797853f37d82f532fde07b',
    'shopprod_59fac084c9ec188eb61e9b84',
    'shopprod_5a83c6219025c9c1788479b9',
    'shopprod_5a9b746b59bbb2ecd4c1b76b',
    'shopprod_5b4cf33c7206c1e1f385eee4',
    'shopprod_5b92b67ccdceed69e8f3803c',
    'shopprod_5be90a8a858d5867a4619c94',
    'shopprod_5c120a68802c07e01e778886',
    'shopprod_5c6a6f5cbe689d2a248cd57a',
    'shopprod_5c70202e7e965de569d56c3a',
    'shopprod_5c98eb4939ce1f3d6a2ccd4e',
    'shopprod_5cde94a9e2343bcf31de5470',
    'shopprod_5d6ace15fb960f7e00a714a8',
    'shopprod_5d784c889fa8e106a8d1b1b1',
    'shopprod_5da9014d07527dd6964a6513',
    'shopprod_5db61da3d481ac25c0dd0d71',
    'shopprod_5e86fc2dda293df9e90cc519',
    'shopprod_5ee00b3fdedb777599a9ed55',
    'shopprod_5f05331e159eecd13e1be168',
    'shopprod_5fb138aeba43b5d2e49e006d',
    'shopprod_61285de8347272611f5bcb18',
    'shopprod_61df2943c5cef23341bfab0a',
    'shopprod_6205b04cdb772b789b714d38',
    'shopprod_6256fd8c4ab1b00f781cfe13',
    'shopprod_6407c25228e358bff5f85782',
    'shopprod_641044143eb5ffaa774be2f3',
    'shopprod_65d17f066e680a1d1f332087',
    'shopprod_664bc0d80cbf8ef829d5d9d4',
    'shopprod_6669d13fdb5ab7f6c7219cd0',
    'shopprod_66713e9732b23a17fab1eb99',
    'shopprod_66cc451106d1067fc121520b',
    'shopprod_66d53f69662bdc49bd9a0f0e',
    'shopprod_6716581892c7014a71f5f7e7',
    'shopprod_67b4dac2d0883cf64f331e0d',
    'shopprod_680ea81c7f41552e88b5896f',
    'shopprod_691ba2c7c8d68595cef13f22',
    'shopprod_6946eac6e93e2a6f508e178d',
    'shopprod_694e8b3554d3fc90efcc0475',
    'shopprod_69bbced560bcfce0f9d3b66a',
    'shopprod_69f7cab766426a593aa5fbac',
    'shopprod_69fb85d75a86416df645fc8f',
    'shopprod_6a323512653f67a1471bf847',
    'shopprod_6a67858b542a6fd916797210',
    'shopprod_6aa8a7ac0c6440310149eeee',
    'shopprod_6acfed0b278532fd3c362446',
    'shopprod_6b5d49c70120237411320a4e',
    'shopprod_6b84f2ef12bbb3b4c33b9356',
    'shopprod_6b90f5905b3fe799ca6547f2',
    'shopprod_6bc771459885e34be170dd4c',
    'shopprod_6c43693c801997feb744ac95',
    'shopprod_6ceddf8b1b31abb3b1a9a3ca',
    'shopprod_6e13770a52ffa391d3c98844',
    'shopprod_6e929aa9445a3c7229452209',
    'shopprod_6f481c5cbb38d125f2806e1a',
    'shopprod_6fbf21b800647372edcb15e2',
    'shopprod_6fefa5c1546f12648c0aecf6',
    'shopprod_70f122558605439e40df0678',
    'shopprod_71e219abc5a1df31ebb5ad1d',
    'shopprod_71fa810ef68bb0ffb03e5317',
    'shopprod_72395764e17d7977e9068d44',
    'shopprod_7246e698fc1254452a9082c8',
    'shopprod_72c251bd58b5c067a189abc3',
    'shopprod_72f0695c91af8e8c1cc115eb',
    'shopprod_7304488b5f9ccd4766e31317',
    'shopprod_73226943d19069df711e762b',
    'shopprod_73466a0e7ed400d98562b018',
    'shopprod_73831b7f522e7f7ae981a73a',
    'shopprod_7417089954b1de82f2b11b8e',
    'shopprod_741f8c341e78266e5b013519',
    'shopprod_7485b70d71abf861c691248b',
    'shopprod_74a433368d2022d91c1a3a25',
    'shopprod_7610f8eff7de610f131bae50',
    'shopprod_7722509c3f64ebd7e788262b',
    'shopprod_773d219076d3f6c2eda90ed3',
    'shopprod_77c6a5a017679c6e0e8a36c7',
    'shopprod_7894006a86cca5c8c9fc3d60',
    'shopprod_78b748da9ae405a08ce65f7b',
    'shopprod_793a0d9b5c35a560466699df',
    'shopprod_7a0969cb41ab5b032d31ea72',
    'shopprod_7a7e2c2075e262295b6472b9',
    'shopprod_7acc3e5a7f4f9cd41c93c967',
    'shopprod_7b9f041c80da25125760ff95',
    'shopprod_7c926b5ce6efe87aca603e00',
    'shopprod_7cfba0ba9d42b8b904b544f9',
    'shopprod_7dd9b111248fa5404c1f04fb',
    'shopprod_7df16f91f21033583844e35a',
    'shopprod_7f706f1a9ad2a8a4a4bd5285',
    'shopprod_7fa084a2cae877dc0aa7c40c',
    'shopprod_7fa92bb757ece623daa1b8d5',
    'shopprod_802902324a83141926129df4',
    'shopprod_8238a2ac3b86851e83293f08',
    'shopprod_8240c90c4282a91d3de6008c',
    'shopprod_829db6c133b99f0a69793e69',
    'shopprod_83153fea5e0fdb682ff76e1b',
    'shopprod_8362191272e90e60ba525fe1',
    'shopprod_8439b99b470c3ce0f1f006ea',
    'shopprod_849a1f82bf468aa4a0af9590',
    'shopprod_852e7793f250d14a5b5a51ab',
    'shopprod_8635dc3c20631db4cf745678',
    'shopprod_866380cdb7963d2ef0fd1a40',
    'shopprod_8670fd80163d98c4387442d9',
    'shopprod_867841c1d8e0b10446f2dd28',
    'shopprod_8737b9d25870b82f30e6b7b5',
    'shopprod_8755bf799c49fe5f1a1aa68f',
    'shopprod_87e5d36b9abaa182055ffc4d',
    'shopprod_8899e8c05df300c748bceb57',
    'shopprod_8980929ac324656155c649ac',
    'shopprod_8a1e9b69c3ec624da9ebda3c',
    'shopprod_8abf749f992cd1a171473d3b',
    'shopprod_8b113a66db88b62bb0510cd1',
    'shopprod_8b136e52329f3a0f9952dfc5',
    'shopprod_8c288669741c7bcee75e6557',
    'shopprod_8c2d966979af2916f0611620',
    'shopprod_8c4785dbc7df105bd73127a8',
    'shopprod_8d0662a5d927a0ad678973c0',
    'shopprod_8daa1c1aa1bea192c3ee2fca',
    'shopprod_8e7cad69654567b52396fb6a',
    'shopprod_8eacbcf914e54dff4ade45a7',
    'shopprod_8f0dbd9e3e6feb06f0bc36ee',
    'shopprod_8f9a7efc2247861386ed09ac',
    'shopprod_9017551fb7a8045cf8d371bb',
    'shopprod_90331af561b1f3516dfca000',
    'shopprod_90626568915385b370b86d60',
    'shopprod_90e6407493d21969349682c5',
    'shopprod_9155c663280359cea9b3acf9',
    'shopprod_918c92a68f20c371a2d0a22d',
    'shopprod_92250e511b79479bb205a047',
    'shopprod_935de5759a24a3c62e1c9f65',
    'shopprod_9386b3ace0777aff436251a0',
    'shopprod_945f03d3489bad00bce1e0db',
    'shopprod_9471f85322b5d84b3063e924',
    'shopprod_94a87f05827052e0a5e2272a',
    'shopprod_960737746e0bdddea4a6c148',
    'shopprod_967bce863873548c94d01a5e',
    'shopprod_969035e6f44dfbe3017d342b',
    'shopprod_96c67914fca890e47c627ebc',
    'shopprod_96f1f1a6ff897afae01f90bb',
    'shopprod_96f4adf55fb609e0640b6d78',
    'shopprod_9702bd05816142ab9dc2f1e0',
    'shopprod_97b11c8c751a2495be1ae832',
    'shopprod_984128e585d02719ea527036',
    'shopprod_9893d041c70bf498ec9a52f6',
    'shopprod_989c801be4e2a9fb01fe5f27',
    'shopprod_98a6d0c28983a8df4c023b77',
    'shopprod_9915266308bdc41e9a3c8eca',
    'shopprod_99580800859f08b9d9daf37b',
    'shopprod_99f10f170addebcc621e766e',
    'shopprod_99f230aa9361e9d41462d203',
    'shopprod_9adef57e3925090f32f8012c',
    'shopprod_9bef13ff24e4aefb16c2ff84',
    'shopprod_9c207859fc2b7da5472866f6',
    'shopprod_9c6996e638bce1fc18fa2d46',
    'shopprod_9c7a715bbf32b1c6bd535ebe',
    'shopprod_9cb864155e11628751a5ad8e',
    'shopprod_9cbe676f102557f9c28acde8',
    'shopprod_9e1685a872124ba29cdca6ff',
    'shopprod_9e28d05831d7387e55f1b8f6',
    'shopprod_9e3cedff0e28482249952dfa',
    'shopprod_9e9c72d24a766a5317a09ff3',
    'shopprod_a03f448b8eae6c645c24c0b1',
    'shopprod_a0b7dbce580487537e93554f',
    'shopprod_a0e95236cd0f40efbf6697c7',
    'shopprod_a21ee8dd52c615fd792d513e',
    'shopprod_a268c34b1057f908aaffc63a',
    'shopprod_a3985cffee2b4dd815204abc',
    'shopprod_a3a0d7fd5d4e74573717f8b8',
    'shopprod_a444181635891f03f9fef0b0',
    'shopprod_a54eac6e836784d28f4e163b',
    'shopprod_a55e83cea894b1464556b50d',
    'shopprod_a64564a559e3295b6eda4bb5',
    'shopprod_a66d8ac0cc555577dd1aaca5',
    'shopprod_a7934b52423e859bdfa594b0',
    'shopprod_a7e6cafc528e4158780d2860',
    'shopprod_a816795897be57b609448f2f',
    'shopprod_a84811d93bb9fb023d89c57f',
    'shopprod_a856a065df460b10c4ed91d8',
    'shopprod_a8d13525b4e5f97558acd7b1',
    'shopprod_a903fa608228e5ab37207f17',
    'shopprod_a995dda3150acdf0138e8f1a',
    'shopprod_a9e06576c9680d3b892e9f2f',
    'shopprod_aa2eb76f3d8e39ecc9e958c4',
    'shopprod_ab2168e33bb10fab677c5f14',
    'shopprod_ac8037352f4d56cc0dbe2279',
    'shopprod_acdd23911f3880d20b8bcf76',
    'shopprod_ace5a9d0b6e092f8b7e4f9c0',
    'shopprod_ad8cc45b33ef80118fc5a9cb',
    'shopprod_aec189c42c6a75fc9860f713',
    'shopprod_af17ba34f22d4175363d319a',
    'shopprod_af37398529513876fbdcb6ab',
    'shopprod_afb7d5513e83a99f5fcfe5b7',
    'shopprod_aff6486e1ec73740059bb34f',
    'shopprod_b0c6749d6385557cdf13a0b5',
    'shopprod_b11cb103862a9dd38ae2c034',
    'shopprod_b17ad388defee8a6a12b118a',
    'shopprod_b270c1fbb537364ee174d138',
    'shopprod_b3e53f4042e2e825cc6a979e',
    'shopprod_b4e79c14026c5e51fd844a33',
    'shopprod_b53db06b8cd74ff14a8e31e3',
    'shopprod_b5a07800c2fb74ceb2044273',
    'shopprod_b5ca26bbfcab76bb4a17a3c1',
    'shopprod_b5d0e2053ac44f4cdc5bf79b',
    'shopprod_b5e465d500586d28e5ecad9c',
    'shopprod_b621c8f0ee383e8312b78b9c',
    'shopprod_b6bb439cdf660f6648aa79ef',
    'shopprod_b6c9ce20a569ea7b06606e8d',
    'shopprod_b7566692de228a478919a3b6',
    'shopprod_b794ac89030dbf09c7e2f4f3',
    'shopprod_b7e3c97960074b9cdc2d0181',
    'shopprod_b8c47f4a26135cb7ab3450db',
    'shopprod_ba045111660aba7358b160fa',
    'shopprod_bab3f07acf202aa4db38c0f6',
    'shopprod_bae209a2f1a4399b8b5fa004',
    'shopprod_bb0ab9232aaedc9428bcb3fd',
    'shopprod_bb42d5811065ef2efe097e87',
    'shopprod_bb988852b512868691668521',
    'shopprod_bc43fd36665e42d730e86886',
    'shopprod_bc7e667ff9900025696441fa',
    'shopprod_bcb5209fe4e7006b6509a3f6',
    'shopprod_bd29748199081b64ed634e53',
    'shopprod_bd463def2908605b122be1db',
    'shopprod_bd6f15ee89f58a93e69bd9ee',
    'shopprod_becb6f88e088d9a231e4314a',
    'shopprod_bf4c4e3a23a453cf3406c6f1',
    'shopprod_c035580c22548904292e2d75',
    'shopprod_c09ca270106d178eb58b630f',
    'shopprod_c1636acbd4d7b24be77cf754',
    'shopprod_c1b9ff82832e04bcad0d790c',
    'shopprod_c1ceed22f5b202dea9be0b59',
    'shopprod_c1cfff23ab0c6f30bc6b7048',
    'shopprod_c1dae755ef0b741fbd17419c',
    'shopprod_c1ea0319a85cab9eaff509ac',
    'shopprod_c2b2ea34cb656177971d8408',
    'shopprod_c35a5709e809678b1ed0ad44',
    'shopprod_c3ab856f5143180d31ce89c2',
    'shopprod_c46a184eaaf1073898481a34',
    'shopprod_c4d797ba1d1a85050152756a',
    'shopprod_c4d81f734e0c472c14ad0693',
    'shopprod_c539510c95693c0067b37a26',
    'shopprod_c54a2760d8041f7efc7f61ba',
    'shopprod_c7413d055fbc7daecd4f5eda',
    'shopprod_c7ca32f5ec32d0011043e7d8',
    'shopprod_c7f2ee5a5edf06e621e03942',
    'shopprod_c94151ef15eff0622a0b64a1',
    'shopprod_c9e9b423198f885b0c54efa5',
    'shopprod_cac6eaff8a2a0bdf68c6b5c6',
    'shopprod_cad7395dcb1790aeb1fcaf97',
    'shopprod_caf03986aa0642ec0d439ed3',
    'shopprod_cbd2a42d045457c69f3f0e29',
    'shopprod_ccb56b6f6e7af2a15a4754c6',
    'shopprod_ce20b0369b2b592586c6d9ab',
    'shopprod_cea170e043a64d1f06b56cc8',
    'shopprod_cf197ebf6f1c7cbc1b7c2314',
    'shopprod_d132315190c5514bcc12258f',
    'shopprod_d164a1c25c97c3bef9d7d6e6',
    'shopprod_d208953800ebd2402c2981aa',
    'shopprod_d21847a8da2baf0c1a50575e',
    'shopprod_d2c73c9320e72269ebc218cc',
    'shopprod_d2e9578e9698b9a1ac2fd4f3',
    'shopprod_d343400e6395f9a200657e10',
    'shopprod_d359c0327f3584d38215a41a',
    'shopprod_d3740b7fcb25ff81b6e1d0d1',
    'shopprod_d399a14c593c0164c31f31c4',
    'shopprod_d4b9c4b00d7d8416a51eaa41',
    'shopprod_d5b7afc5511ce73c09a30df9',
    'shopprod_d5cd565e3618fc529dc763c0',
    'shopprod_d5de1ec0cf6d33e877596a67',
    'shopprod_d63f9360f58dc6701d00ee3b',
    'shopprod_d6a2873acf29974e1ef7aac2',
    'shopprod_d6aa87cad22547b9b3567cda',
    'shopprod_d6bdf401b3428370a54443a6',
    'shopprod_d822f119d165776d111fb192',
    'shopprod_d86116926dde0e7091fd64ad',
    'shopprod_d939f1dd48bfdbf119701942',
    'shopprod_da53c3008b02fd39442f7035',
    'shopprod_dac0ee461805fcf51e836a79',
    'shopprod_dade7cdabf0be47bfeb3931b',
    'shopprod_db48f88871ef18a96cba7c92',
    'shopprod_db638e1d827b6f2b0fefcc63',
    'shopprod_dbeb74e09929696824e7e4c7',
    'shopprod_dc453936b48f7523447169df',
    'shopprod_dcea7ecfec0f53ddc2a4e807',
    'shopprod_dcf816de3d714468fc002bb9',
    'shopprod_dcfb5899b928facff30a0a62',
    'shopprod_de3e76e312ec2930b2f401e2',
    'shopprod_de5ef70aff708778107dcdfb',
    'shopprod_dee38132530e951d8cc875d3',
    'shopprod_df7f28ba513c7d8a5ea7c512',
    'shopprod_dfb8b1779e35ddcb036ce05d',
    'shopprod_dfe33bd9e89f07b72e62dd0f',
    'shopprod_e040b063aa4b59ce132a9b74',
    'shopprod_e0856f30a072503d78d823f1',
    'shopprod_e0c6f411948f1c1fbbeb434d',
    'shopprod_e133d621f92acaa9b23c5530',
    'shopprod_e172b27e1ec5d8f95d635128',
    'shopprod_e21bb4cb59246360065d278c',
    'shopprod_e2200d39618f0438fe380d2e',
    'shopprod_e31a3d7e9f96153ba5954240',
    'shopprod_e3257b7a42ad7edd2b7689b1',
    'shopprod_e335c59f776d5f11ca133226',
    'shopprod_e33d7c6d28056e2dc887432e',
    'shopprod_e343f8a81b8456dcecf51822',
    'shopprod_e35a526f5c5effc986e8ae9b',
    'shopprod_e3840c53a5b00cccbf0169fc',
    'shopprod_e47a909a6eb982ea228435be',
    'shopprod_e4995378aa3a29c6fabab6e6',
    'shopprod_e4b7a8f948b751f0340539c7',
    'shopprod_e5b7d6cce6b80a632236de1c',
    'shopprod_e699f99cb6614d4346385a56',
    'shopprod_e708839ce83074c8f7edabf1',
    'shopprod_e7594e08ec1064c1d3dbfe3c',
    'shopprod_e772d0f943d904cf84f0c907',
    'shopprod_e850203716a69fc9ad29e633',
    'shopprod_e889719d66a533416f8e18d8',
    'shopprod_e8a4060c1612e318e040bf6e',
    'shopprod_e8fc55cdcd944ca1f2323a69',
    'shopprod_e961e2913779dd0a2cf4ac3c',
    'shopprod_ea506c88ae381b80361ad66f',
    'shopprod_eb318145a0095dbd171be10a',
    'shopprod_eb8fb564f34604c12407e09c',
    'shopprod_eb952b1613d6d358e1408d99',
    'shopprod_eba879d7b0e37a249c1444ff',
    'shopprod_ebabb9840b521a7dc3e92e7c',
    'shopprod_ec8ea38ad78743af09567379',
    'shopprod_ed1d894979b684deed0564e0',
    'shopprod_ed761473114758619ff11bed',
    'shopprod_ef53f511396b3b781d46fb97',
    'shopprod_f0288d454e89a9da81b43cdd',
    'shopprod_f04f03874946fbfb1f593cbe',
    'shopprod_f12a513bd7950b1aab240070',
    'shopprod_f14691bf1dbfca31776d53a9',
    'shopprod_f1fb7b6244af4f9f19197bc9',
    'shopprod_f229743fa676418e93f65b93',
    'shopprod_f22b3e8c5b298b2f7e2c4d6e',
    'shopprod_f267d99c3c4d6a9cf2a38ca8',
    'shopprod_f316522592c6330d42d22a32',
    'shopprod_f372c64305c8018667dfcf54',
    'shopprod_f4173a40131bab9740280470',
    'shopprod_f4ba1cf5141eaeba58e0a2de',
    'shopprod_f56769b50033105340c4633c',
    'shopprod_f5edb374382b8a573f9783f0',
    'shopprod_f6d1b7c4b6dd9ee3010f449e',
    'shopprod_f78c18335d096406de2f0a7c',
    'shopprod_f84dd26cb53db1f0568e871d',
    'shopprod_f87189668d6faf75f9ebc546',
    'shopprod_f8730e0832b2c264b61e7e68',
    'shopprod_f8e1643cb7c61d630a3e120d',
    'shopprod_f8ff06843d6706926f16921a',
    'shopprod_f929febec007fa5dd0bd55db',
    'shopprod_fa3447d61ff2a4fc148118d4',
    'shopprod_fadfcaec2ca559f8071b0565',
    'shopprod_fb0dabdb14744fd1a64630ab',
    'shopprod_fb150db733a33c5a4ad7b884',
    'shopprod_fb2f5e5c9cdd2dcdec1a2ab6',
    'shopprod_fb71137fb7842b5b8fdbdb0e',
    'shopprod_fb79016851743f919dcc5e1b',
    'shopprod_fb896afaa211231ce52bbc27',
    'shopprod_fc3294bbac70719b0ecf0448',
    'shopprod_feb4c1d83dace0ce327d47b2',
    'shopprod_febbff7aef68ad2bfe7a66a6',
    'shopprod_fee7d5e6d56681f8d9162b7f',
    'shopprod_ff7ce5e3a18aab687daec9cc',
    'shopprod_ffc4644d63915408481589a1',
    'shopprod_ffdd2bd8f962e3bfcd1b4a54',
})
DIVNIX_MAGNETIC_RING_V12_IDS = frozenset({
    'shopprod_030f56535ef43e293768940a',
    'shopprod_12426ebea9822b72d23a6a0d',
    'shopprod_1c00bb6794cefd0e43710c88',
    'shopprod_1f3c056be7fab32da25811a4',
    'shopprod_21cb501a74dfcf63cfb9bce4',
    'shopprod_258cfb252b29093e299d40cd',
    'shopprod_2e1e39ad17788f83c475aec6',
    'shopprod_2e3d3a7d88628feec52eb0af',
    'shopprod_360b8aef425e3083e27dc76c',
    'shopprod_3b59dfe49ec7707f8d632dcb',
    'shopprod_4e016955801246852510dd98',
    'shopprod_53aace90c8db02415bfa097f',
    'shopprod_66713e9732b23a17fab1eb99',
    'shopprod_680ea81c7f41552e88b5896f',
    'shopprod_69fb85d75a86416df645fc8f',
    'shopprod_6a67858b542a6fd916797210',
    'shopprod_6bc771459885e34be170dd4c',
    'shopprod_73226943d19069df711e762b',
    'shopprod_7b9f041c80da25125760ff95',
    'shopprod_7fa084a2cae877dc0aa7c40c',
    'shopprod_83153fea5e0fdb682ff76e1b',
    'shopprod_8c2d966979af2916f0611620',
    'shopprod_960737746e0bdddea4a6c148',
    'shopprod_96f1f1a6ff897afae01f90bb',
    'shopprod_9702bd05816142ab9dc2f1e0',
    'shopprod_99f230aa9361e9d41462d203',
    'shopprod_a0e95236cd0f40efbf6697c7',
    'shopprod_ace5a9d0b6e092f8b7e4f9c0',
    'shopprod_b3e53f4042e2e825cc6a979e',
    'shopprod_b6c9ce20a569ea7b06606e8d',
    'shopprod_b7566692de228a478919a3b6',
    'shopprod_c7f2ee5a5edf06e621e03942',
    'shopprod_d21847a8da2baf0c1a50575e',
    'shopprod_de3e76e312ec2930b2f401e2',
    'shopprod_dfb8b1779e35ddcb036ce05d',
    'shopprod_e31a3d7e9f96153ba5954240',
    'shopprod_e335c59f776d5f11ca133226',
    'shopprod_e4b7a8f948b751f0340539c7',
    'shopprod_e772d0f943d904cf84f0c907',
    'shopprod_f267d99c3c4d6a9cf2a38ca8',
    'shopprod_f5edb374382b8a573f9783f0',
    'shopprod_f78c18335d096406de2f0a7c',
    'shopprod_f929febec007fa5dd0bd55db',
})

# V13 exact-SKU conditional Chapter 64 footwear review: 102 current
# unclassified Footwear listings with an identified footwear subcategory.
# Physical pair, upper/sole HSN, discounts and actual transaction
# sale value MUST be checked; no automatic GST approval.
FOOTWEAR_CATEGORY_V13_IDS = frozenset({
    'shopprod_01da4139ab218d0c97a1d9cc',
    'shopprod_074925886922720120bd4c0d',
    'shopprod_07d219410eae552e95594d18',
    'shopprod_0e5c11d7c54563f5ff59ec05',
    'shopprod_1edd00471f898b04923c3564',
    'shopprod_2176ff961f780fd181d65b2b',
    'shopprod_2a6f66461a879ce6ae161253',
    'shopprod_2fc61934725a0c68c3efaae0',
    'shopprod_3044d4255de83145305a5e3d',
    'shopprod_309b607f2a5624483951377d',
    'shopprod_33d1ab4d962a3ca6dccbbfd3',
    'shopprod_33fe1f28c0cb92ccde2ac56c',
    'shopprod_38559072c367c1fdf79d7cb8',
    'shopprod_3f333cd866fe0c06f42d21b9',
    'shopprod_3f9ff3651fe7120a726d25cd',
    'shopprod_40c2c82a8029934b8aee736c',
    'shopprod_49f321be329d7ae9094a5a3d',
    'shopprod_4ec800c1dc964a49985363ed',
    'shopprod_4f809cb7826bd29d79e38a3d',
    'shopprod_51bbdbed946c5b039388b433',
    'shopprod_51e7e6b271beac70b9cde5db',
    'shopprod_52fcf25bfc42b041e328c1cf',
    'shopprod_53e0328c1d163e8d1144805b',
    'shopprod_547e2e72c0bd94fbbb34eba6',
    'shopprod_58f51bb773fb7af4a2774e23',
    'shopprod_59cbe72f82d75fe98604b3fd',
    'shopprod_5ae10be3ab14a8af770725b0',
    'shopprod_5ae6c727ce44a6637235d815',
    'shopprod_5c63c1f1c34683cc73097925',
    'shopprod_5e086ed048c796f754ca682a',
    'shopprod_5f1465f6df4306e4b3f3937d',
    'shopprod_5f72c09783815f62bbc47cec',
    'shopprod_6066be6a0305055652aaba0c',
    'shopprod_6567477aa7dce21d075fa88e',
    'shopprod_65987213c25b4d8207fbf8c4',
    'shopprod_664326a553f8f25b68096ba8',
    'shopprod_66624750e5a8bde91236d804',
    'shopprod_686c76a8f2e26bb428e8398c',
    'shopprod_69cb39cdee8274a8ed54a884',
    'shopprod_6b28b4711f4f09714319e811',
    'shopprod_6d0f06fd19b9d80013c97b06',
    'shopprod_6f492111474fdd8b886ae507',
    'shopprod_6fac6dc802100baf16114a38',
    'shopprod_75af6e46d885333b55142080',
    'shopprod_78e8f270211a53ecfca109cb',
    'shopprod_7b0bc99106458e86d919ef18',
    'shopprod_7d9e1e9e2ffe0d5f6f8c3552',
    'shopprod_7df1ef1f355dc65361ba9f0f',
    'shopprod_7eea6db48405fb1e012e4d3e',
    'shopprod_7f2949031959d1ee66bafa5e',
    'shopprod_801b55186d17ab91c14df8ef',
    'shopprod_809ac3fd6b8d347ee7cefb4a',
    'shopprod_81d1df0a6388d8e93b1e9d1f',
    'shopprod_8206bccb8afdb9c4a14c52d1',
    'shopprod_824b7685fc3a717503f7bbf6',
    'shopprod_837e77118f901d1136c13b22',
    'shopprod_849b4968adf5e80bd0928c7c',
    'shopprod_8f1fe79613ef4ca2fa1366d8',
    'shopprod_a0f6809e6a6639fad2611b00',
    'shopprod_a25e7be7bc65dcfa9dbcba03',
    'shopprod_a759f01b17226f1dab5f2e5b',
    'shopprod_a99e83de4eb9d6741977c40c',
    'shopprod_acc5ca0e25b629a6c17e7f14',
    'shopprod_ae0c95b7a7a85806b5a98a62',
    'shopprod_ae7c19546c3dd68c448163ae',
    'shopprod_af3fa086dc6c7b3c288eb942',
    'shopprod_afbf73dfe51622589a1cdbfc',
    'shopprod_b2f4958ed5b119f2c16bb3ca',
    'shopprod_b4aa6dcdceebd495b290183b',
    'shopprod_b720953e0cf4e0cdd7654417',
    'shopprod_c4cf47271df10e6b82b1f913',
    'shopprod_c5c8a77c8f2d76496f2288d7',
    'shopprod_c67bb18aa247ed688fac0305',
    'shopprod_c8f4468a65bf3e0440df3d9c',
    'shopprod_c94cd486bdb5c56aa37eae98',
    'shopprod_c9a3f12948fa9eece8939e01',
    'shopprod_cdc4314706baf152a021a5e0',
    'shopprod_d24a52a877dabac6c069e890',
    'shopprod_d2624122b7781629058fcce8',
    'shopprod_d29d8c9c612bca0b922d8484',
    'shopprod_d34f60ce997945803b013ebb',
    'shopprod_d48a62f8d8aadb1710bb9879',
    'shopprod_d959d544b1433364ef6401d6',
    'shopprod_d9b287d3c660731a3e4807f0',
    'shopprod_d9f519026d8143b57d8095e9',
    'shopprod_ddec57c4dfe71cb9709b8e40',
    'shopprod_e2c273a4ec9d15c9ffe6a9b8',
    'shopprod_e737ebac737a8fad16102e0a',
    'shopprod_e80d37d84b8f4da444761d97',
    'shopprod_e8f107d6b6874bd430718a17',
    'shopprod_e966559da5d0b9bb4fbc7f2e',
    'shopprod_ea59a63315138d6e72af3480',
    'shopprod_ed76c0734ac767fdcc5a8f3a',
    'shopprod_efcff825607e4b533020b79b',
    'shopprod_f57e59e3b3ea11cdbd254ae6',
    'shopprod_f78d87e0afd2a54f0cab0a95',
    'shopprod_f7f022eafc0dad09f52ad752',
    'shopprod_f8aa869c454f839fd28f2534',
    'shopprod_fab0102dcffd3f9d27d00c56',
    'shopprod_fd1ef0652df67b2708c948fe',
    'shopprod_fd768c9c30b17906155afb27',
    'shopprod_fdc4ef4c81d2605a174089c5',
})

# 2025 notification: narrow daily-use categories at 5%. These name matches
# are CONDITIONAL only; no automatic registry approval or invoice issuance.
# Products classed as medicines, industrial goods or combined kits need review.
DAILY_USE_EXCLUSIONS = re.compile(
    r"\b(?:liquid soap|liquid hand wash|hand wash|body wash|"
    r"shower gel|soap dispenser|soap dish|soap holder|syndet|"
    r"industrial soap|laundry soap|washing soap|dish soap|"
    r"detergent|medicated soap|medicated shampoo|therapeutic shampoo|toothbrush holder|electric toothbrush|"
    r"soap tray|combo kit|gift set)\b",re.IGNORECASE
)
DAILY_USE_FAMILIES = (
    (re.compile(r"\bshampoos?\b",re.IGNORECASE),"3305","shampoo"),
    (re.compile(r"\bhair\s+oils?\b",re.IGNORECASE),"3305","hair oil"),
    (re.compile(r"\btoothpastes?\b",re.IGNORECASE),"3306","toothpaste"),
    (re.compile(r"\btoothbrush(?:es)?\b",re.IGNORECASE),"9603","toothbrush"),
    (re.compile(r"\b(?:toilet|bath|beauty|antibacterial|herbal)?\s*soaps?\b",re.IGNORECASE),
     "3401","toilet soap bar"),
)

EXPORT_FIELDS = (
    "productId", "productName", "category", "customerPrice", "suggestedGstRate",
    "hsnFamily", "effectiveFrom", "source", "rule", "confidence",
    "reviewReason", "priceSensitive", "approval",
)


def customer_price(product: dict[str, Any]) -> Decimal | None:
    """Use customer-facing gross price, not vendor supply cost or MRP."""
    try:
        if product.get("customerPricePaise") is not None:
            return (Decimal(str(product["customerPricePaise"])) / 100).quantize(Decimal(".01"))
        if product.get("price") is not None:
            return Decimal(str(product["price"])).quantize(Decimal(".01"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return None


def suggest(product: dict[str, Any]) -> dict[str, Any]:
    """Pure proposal: NEVER authorizes invoice issue or tax registry writes."""
    name = str(product.get("name") or "")
    category = str(product.get("category") or "")
    brand = str(product.get("brand") or "")
    price = customer_price(product)
    candidate = {
        "rate": None, "hsnFamily": "", "confidence": "UNCLASSIFIED",
        "rule": "", "reason": "Insufficient verified HSN/material/product attributes",
        "priceSensitive": False, "source": "", "effectiveFrom": "",
        "autoApplyEligible": False,
    }
    if (
        (brand.casefold() == "casio" or name.casefold().startswith("casio "))
        and CASIO.search(name) and not NOT_WATCH.search(name)
        and not re.search(r"\b(?:gold\s+plated|precious\s+metal|solid\s+gold)\b", name, re.I)
    ):
        candidate.update({
            "rate": "18", "hsnFamily": "9102", "confidence": "HIGH",
            "rule": "9102: conventional Casio F-91W/A158WA wristwatch",
            "reason": "Verify model is conventional non-precious-metal watch, not an accessory",
            "source": GOODS_RATE_SOURCE,
            "effectiveFrom": RATE_EFFECTIVE_DATE,
            "autoApplyEligible": False,
        })
        return candidate
    if category == "Footwear" and FOOTWEAR.search(name):
        if price is None or price <= 0:
            candidate["reason"] = "Footwear sale value missing; cannot apply Rs 2,500 rule"
            return candidate
        candidate.update({
            "rate": "5" if price <= THRESHOLD else "18",
            "hsnFamily": "64",
            "confidence": "CONDITIONAL",
            "rule": "Chapter 64 footwear sale value <= Rs 2,500: 5%; above: 18%",
            "reason": "Confirm product is one footwear pair; coupons, variants and future price changes can alter rate",
            "priceSensitive": True, "source": GOODS_RATE_SOURCE,
            "effectiveFrom": RATE_EFFECTIVE_DATE,
        })
        return candidate
    if category == "Clothing & Fashion" and APPAREL.search(name):
        if FOOTWEAR.search(name):
            candidate["reason"]="Ambiguous category: possible footwear listed under fashion"
            return candidate
        if price is None or price <= 0:
            candidate["reason"]="Apparel sale value missing; cannot apply Rs 2,500 rule"
            return candidate
        candidate.update({
            "rate": "5" if price <= THRESHOLD else "18",
            "hsnFamily": "61/62",
            "confidence": "CONDITIONAL",
            "rule": "Chapter 61/62 readymade apparel sale value <= Rs 2,500: 5%; above: 18%",
            "reason": "Confirm finished apparel per piece and price after discounts; HSN 61 vs 62 needs fabric construction",
            "priceSensitive": True, "source": GOODS_RATE_SOURCE,
            "effectiveFrom": RATE_EFFECTIVE_DATE,
        })
        return candidate
    if category == "Beauty & Personal Care" and not DAILY_USE_EXCLUSIONS.search(name):
        for pattern, hsn, kind in DAILY_USE_FAMILIES:
            if not pattern.search(name):
                continue
            # Soap is lower confidence when a bar/cake isn't explicit:
            # ambiguous cosmetic cleansing products must not be assigned
            # an invoice rate based on the word soap alone.
            if kind=="toilet soap bar" and re.search(
                r"\b(?:cream|gel|lotion|cleanser|spray|foam|oil)\b",name,re.I
            ):
                continue
            candidate.update({
                "rate":"5",
                "hsnFamily":hsn,
                "confidence":"CONDITIONAL",
                "rule":f"Daily-use {kind}: 5% in 2025 official GST schedule",
                "reason":(
                    "Verify exact formulation, retail product form and tariff heading. "
                    "Exclude medicaments, mixed kits and specialised preparations; "
                    "a name match is not a final tax classification."
                ),
                "priceSensitive":False,
                "source":GOODS_RATE_SOURCE,
                "effectiveFrom":RATE_EFFECTIVE_DATE,
            })
            return candidate
    # Official notification 9/2025 IGST Schedule II serial 482, HSN 8509.
    # These are CONDITIONAL product-type matches; powered motor, retail
    # kit composition and exact tariff heading must be checked.
    if (
        category == "Home & Living"
        and str(product.get("subcategory") or "").casefold()=="kitchen appliances"
        and re.search(
            r"\b(?:mixer\s*[- ]?grinder|juicer\s*[- ]?mixer\s*[- ]?grinder)\b",
            name,re.I
        )
        and not re.search(
            r"\b(?:manual|hand[ -]?operated|toy|replacement|spare|"
            r"blade\s+only|jar\s+only|attachment|non[ -]?electric)\b",
            name,re.I
        )
    ):
        candidate.update({
            "rate":"18",
            "hsnFamily":"8509",
            "confidence":"CONDITIONAL",
            "rule":"HSN 8509 motorised domestic mixer-grinder: 18%, Schedule II serial 482",
            "reason":(
                "Confirm self-contained electric motor and household use. "
                "Check product label/model, supply of whole appliance rather "
                "than spare jars, and effective statutory rate."
            ),
            "priceSensitive":False,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    # Official notification 9/2025: Chapter 63 made-up textiles, Schedule I
    # serial 390 up to INR 2500 per piece and Schedule II serial 199 above.
    # Name/price alone do not establish per-piece value or exact 6302/6307.
    if (
        category=="Home & Living"
        and str(product.get("subcategory") or "").casefold()=="bath linens"
        and re.search(r"\b(?:bath|hand|face|hair|cleaning)\s+towel\b",name,re.I)
        and not re.search(
            r"\b(?:paper|dispenser|holder|hook|rail|rack|bar|toy)\b",name,re.I
        )
    ):
        if price is None or price<=0:
            candidate["reason"]="Textile towel: current selling price absent; verify per-piece threshold"
            return candidate
        candidate.update({
            "rate":"5" if price<=THRESHOLD else "18",
            "hsnFamily":"63",
            "confidence":"CONDITIONAL",
            "rule":"Chapter 63 made-up textile article sale value <= Rs 2,500: 5%; above: 18%",
            "reason":(
                "Verify textile composition, towel/linen classification, "
                "number of pieces per pack and sale value per piece. "
                "Sets, price changes and discounts may affect this proposal."
            ),
            "priceSensitive":True,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    # Schedule I of Notification 9/2025: tea/coffee, preserved fruits,
    # mixed condiments, and cereal flake products. Name-only matches are
    # CONDITIONAL; verify packaging, ingredients and exact HSN before approval.
    if category=="Groceries":
        subcategory=str(product.get("subcategory") or "")
        grocery_match=None
        if subcategory=="Tea & Coffee":
            if re.search(r"\bcoffee\b",name,re.I) and not re.search(
                r"\b(?:coffee-flavoured|coffee flavored|coffee flavor|candy|"
                r"chocolate|coffee mug|coffee mixer|coffee machine)\b",name,re.I
            ):
                grocery_match=("0901/2101","Roasted or soluble coffee",
                    "Confirm whether roasted coffee (0901) or soluble extract/preparation "
                    "(2101), ingredient list and retail package.")
            elif re.search(r"\btea\b",name,re.I) and not re.search(
                r"\b(?:herbal|tulsi detox|kahwa|tea masala|tea infuser|"
                r"tea maker|tea pot|tea biscuits)\b",name,re.I
            ) and not (re.search(r"\btulsi\b",name,re.I) and not re.search(
                r"\bgreen\s+tea\b",name,re.I
            )):
                grocery_match=("0902","Tea",
                    "Verify actual tea leaves (Camellia sinensis), rather than herbal "
                    "infusion, and confirm ingredients/retail packaging.")
        elif subcategory=="Jams, Honey & Spreads":
            if re.search(r"\b(?:fruit|strawberry|mango|mixed fruit)\s+jam\b",name,re.I):
                grocery_match=("2007","Cooked fruit jam",
                    "Confirm cooked fruit jam rather than sweet spread, syrup or non-fruit paste.")
            elif re.search(r"\bmayonnaise\b",name,re.I):
                grocery_match=("2103","Prepared mayonnaise sauce",
                    "Verify packaged mayonnaise is sauce/condiment heading 2103.")
            elif re.search(r"\bnatural honey\b",name,re.I):
                grocery_match=("0409","Packaged natural honey",
                    "Verify natural rather than artificial honey, pre-packaged and labelled.")
        elif subcategory=="Breakfast Cereals" and re.search(
            r"\bcorn\s+flakes\b",name,re.I
        ) and not re.search(r"\b(?:uncooked|loose grain)\b",name,re.I):
            grocery_match=("1904","Prepared corn flakes",
                "Verify ready-to-eat prepared cereal flakes instead of raw corn or flour.")
        if grocery_match:
            hsn,kind,reason=grocery_match
            candidate.update({
                "rate":"5",
                "hsnFamily":hsn,
                "confidence":"CONDITIONAL",
                "rule":f"Schedule I qualifying {kind}: 5%",
                "reason":reason+" Exact tariff item must be verified before tax invoice.",
                "priceSensitive":False,
                "source":GOODS_RATE_SOURCE,
                "effectiveFrom":RATE_EFFECTIVE_DATE,
            })
            return candidate
    # Schedule II of Notification 9/2025: cosmetics / skin preparations
    # excluding medicines and Schedule I talcum powder/face powder.
    if category=="Beauty & Personal Care":
        if not re.search(
            r"\b(?:medicated|medicinal|therapeutic|rx|prescription|"
            r"diaper rash|balm|antifungal|antiseptic|medicine|"
            r"talcum|face powder|baby powder|gift set|assorted gift)\b",name,re.I
        ):
            cosmetic_match=None
            if re.search(r"\b(?:face serum|skin serum|sunscreen)\b",name,re.I):
                cosmetic_match=("3304","Face serum or sunscreen skin-care preparation",
                    "Confirm non-medicinal cosmetic formulation and packaged composition.")
            elif re.search(
                r"\b(?:body lotion|skin cream|face cream|face moisturiser|"
                r"face moisturizer|baby lotion)\b",name,re.I
            ):
                cosmetic_match=("3304","Skin-care cream or body lotion",
                    "Confirm cosmetic skin preparation not a medicament or medical treatment.")
            elif re.search(r"\bhair conditioner\b",name,re.I) and not re.search(
                r"\b(?:shampoo|hair oil)\b",name,re.I
            ):
                cosmetic_match=("3305","Hair conditioner (other hair preparation)",
                    "Confirm independent hair conditioner; exclude shampoo or combined kit.")
            elif re.search(r"\b(?:perfume|eau de parfum|toilet water)\b",name,re.I):
                cosmetic_match=("3303","Perfume or toilet water",
                    "Confirm cosmetic fragrance rather than air freshener/medicinal formulation.")
            if cosmetic_match:
                hsn,kind,reason=cosmetic_match
                candidate.update({
                    "rate":"18",
                    "hsnFamily":hsn,
                    "confidence":"CONDITIONAL",
                    "rule":f"Schedule II qualifying {kind}: 18%",
                    "reason":reason+" Final tariff heading requires product-label review.",
                    "priceSensitive":False,
                    "source":GOODS_RATE_SOURCE,
                    "effectiveFrom":RATE_EFFECTIVE_DATE,
                })
                return candidate
    # Bedding: made-up textile articles Chapter 63, Schedule I item 390
    # at sale value <= INR 2500/piece; Schedule II item 199 above.
    # CRITICAL: bundle contents / invoice transaction value / textile material
    # must be checked. The SKU's gross visible price is only a preliminary
    # clue, never a legally binding tax rate or approval.
    if (
        category=="Home & Living"
        and str(product.get("subcategory") or "").casefold()=="bedsheet & bed covers"
        and re.search(
            r"\b(?:bed\s*sheet|bedsheet|bed\s*cover|bedcover|bedspread)\b",name,re.I
        )
        and not re.search(
            r"\b(?:quilt|comforter|duvet|mattress|protector|pillow\s+only|"
            r"pillowcase\s+only|fitted\s+foam|wall\s+cover)\b",name,re.I
        )
    ):
        if price is None or price<=0:
            candidate["reason"]="Made-up bed linen: selling price not available for provisional review"
            return candidate
        candidate.update({
            "rate":"5" if price<=THRESHOLD else "18",
            "hsnFamily":"6302/6304",
            "confidence":"CONDITIONAL",
            "rule":"Chapter 63 made-up bed linen; 5% up to Rs 2,500 per piece, 18% above",
            "reason":(
                "Confirm 6302 versus 6304, fabric and packaging; verify actual "
                "transaction sale value per piece, and price allocation where "
                "bed sheet is sold with pillowcases or other articles. "
                "Current gross listing price is not conclusive."
            ),
            "priceSensitive":True,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate

    # Only identifiable single spices, NOT blended masala or preparations.
    # Item 36-42 Schedule I, mixed sauces/seasonings require separate 2103
    # review. Do not infer packaging, formulation, or GST invoice treatment.
    if (
        category=="Groceries"
        and str(product.get("subcategory") or "").casefold()=="sugar, salt & spices"
        and not re.search(
            r"\b(?:masala|blend|mix|seasoning|sauce|paste|ready|"
            r"hing|asafoetida|salt|sugar|flavour|flavor)\b",name,re.I
        )
    ):
        spice=None
        if re.search(r"\b(?:chilli|chili|lal mirch|red pepper)\b",name,re.I):
            spice=("0904","Dried ground chilli/paprika")
        elif re.search(r"\b(?:coriander|dhania)\b",name,re.I):
            spice=("0909","Coriander seed, ground or whole")
        elif re.search(r"\b(?:cumin|jeera)\b",name,re.I):
            spice=("0909","Cumin seed, ground or whole")
        elif re.search(r"\b(?:turmeric|haldi)\b",name,re.I):
            spice=("0910","Dried turmeric powder or root")
        elif re.search(r"\b(?:elaichi|cardamom)\b",name,re.I):
            spice=("0908","Cardamom")
        if spice:
            hsn,form=spice
            candidate.update({
                "rate":"5",
                "hsnFamily":hsn,
                "confidence":"CONDITIONAL",
                "rule":f"Single spice ({form}): 5%, 2025 Schedule I",
                "reason":(
                    "Verify retail contents are the stated pure dry spice and "
                    "not a mixed condiment, spice preparation, seed-quality "
                    "stock or fresh exempt item; match supplier label/HSN."
                ),
                "priceSensitive":False,
                "source":GOODS_RATE_SOURCE,
                "effectiveFrom":RATE_EFFECTIVE_DATE,
            })
            return candidate
    # Government Notification 9/2025, Schedule II serial 584 (HSN 9102),
    # 18% for conventional wrist watches other than heading 9101.
    # Names alone cannot distinguish a conventional watch from a smartwatch,
    # 9101 precious-metal-cased watch, bundled articles or replacement parts.
    # Every match is CONDITIONAL with no auto-approval or invoice issuance.
    if (
        category in ("Accessories","Clothing & Fashion")
        and str(product.get("subcategory") or "").casefold() in
            ("watches","ladies watch","men's watches","women's watches")
        and re.search(r"\b(?:wrist\s*watch|wristwatch|watches|watch)\b",name,re.I)
        and not re.search(
            r"\b(?:smart\s*[- ]?watch|smartwatch|fitness\s*tracker|"
            r"band|strap|replacement|charger|case\s+only|"
            r"watch\s+case|watch\s+protector|accessory|"
            r"bracelet|combo|gift\s+set|set\s+of|"
            r"solid\s+gold|precious\s+metal|gold\s+clad|"
            r"bluetooth|touch\s*screen)\b",name,re.I
        )
    ):
        candidate.update({
            "rate":"18",
            "hsnFamily":"9102",
            "confidence":"CONDITIONAL",
            "rule":"Ordinary non-precious-metal-cased wristwatch: 18%, Schedule II serial 584",
            "reason":(
                "Verify physical watch movement and case material, rather "
                "than smartwatch/heading 9101 precious-metal-cased goods. "
                "Confirm a single complete watch, not a strap, watch-and-jewellery "
                "combo or bundled kit. Check model and original supplier invoice."
            ),
            "priceSensitive":False,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    # 2025 Notification No. 9/2025 IGST Schedule I.
    # These retail grocery item names are clues, never proof of packaging,
    # composition, tariff code, or exemption. Owner must review labels
    # before classification or issue of GST tax invoice.
    if category=="Groceries":
        sub=str(product.get("subcategory") or "").casefold()
        staple=None
        if sub=="rice & other grains":
            if re.search(r"\b(?:poha|chirwa|flattened rice)\b",name,re.I):
                staple=(
                    "1904","pre-packaged and labelled flattened rice",
                    "Check poha/chira is pre-packaged and labelled; confirm it is "
                    "flattened beaten rice rather than raw/milled rice."
                )
            elif re.search(r"\b(?:rice|chawal|basmati)\b",name,re.I) and not re.search(
                r"\b(?:rice bran|rice oil|rice flour|rice noodles|rice snacks|"
                r"unpacked|loose|bulk|snack|cooked|ready[- ]?to[- ]?eat)\b",name,re.I
            ):
                staple=(
                    "1006","pre-packaged and labelled rice",
                    "Verify pre-packaged-and-labelled status, net package weight "
                    "and supplier invoice. Loose/bulk rice can have different "
                    "exemption treatment; do not auto-approve based on title."
                )
        elif sub=="oils & ghee":
            if re.search(r"\bghee\b",name,re.I) and not re.search(
                r"\b(?:imitation|vegetable ghee|vanaspati ghee|ghee flavou?r)\b",name,re.I
            ):
                staple=(
                    "0405","milk-fat ghee",
                    "Confirm genuine dairy milk fat/ghee, rather than vegetable "
                    "fat substitute or mixed preparation, from supplier label."
                )
            elif re.search(r"\b(?:soya[\s-]?bean|soyabean)\s+oil\b",name,re.I):
                staple=(
                    "1507","soya-bean edible oil",
                    "Confirm pure edible soya-bean oil, not a mixture or chemically "
                    "modified preparation; supplier label and invoice required."
                )
            elif re.search(r"\b(?:mustard|kachi\s+ghani\s+mustard)\s+oil\b",name,re.I):
                staple=(
                    "1514","mustard edible oil",
                    "Confirm mustard oil and not compound or blended cooking oil; "
                    "supplier label and invoice required."
                )
            elif re.search(r"\bsunflower\s+oil\b",name,re.I):
                staple=(
                    "1512","sunflower-seed edible oil",
                    "Confirm actual edible sunflower-seed oil rather than mixed "
                    "or chemically modified oils; verify supplier composition."
                )
            elif re.search(r"\brice\s+bran\s+oil\b",name,re.I):
                staple=(
                    "1515","rice-bran edible oil",
                    "Confirm rice-bran oil under other fixed vegetable oils, "
                    "excluding blends and chemically modified preparations; "
                    "verify supplier invoice and ingredients."
                )
            elif re.search(r"\bvanaspati\b",name,re.I) and not re.search(
                r"\bghee\b",name,re.I
            ):
                staple=(
                    "1516/1517","vanaspati edible hydrogenated/mixed fat",
                    "Confirm hydrogenation/process and whether the item falls "
                    "under 1516 or 1517; verify ingredient label, supplier HSN."
                )
        elif sub=="sugar, salt & spices":
            if re.search(r"\b(?:refined sugar|sugar|cheeni)\b",name,re.I) and not re.search(
                r"\b(?:flavoured|flavored|sweetener|jaggery|khandsari|"
                r"salt|mix|candy|sugar-free)\b",name,re.I
            ):
                staple=(
                    "1701","cane/beet refined or ordinary sugar",
                    "Confirm cane/beet sugar or chemically pure sucrose under "
                    "1701, not jaggery, khandsari, rab or other sugar confectionery."
                )
            elif re.search(r"\b(?:chaa?t masala|kitchen king|sabzi masala)\b",name,re.I):
                staple=(
                    "2103","mixed condiment/seasoning",
                    "Verify an actual mixture/preparation of spices rather than "
                    "single dried pure spice; check ingredients and supplier HSN."
                )
        elif sub=="jams, honey & spreads":
            if re.search(r"\bhoney\b",name,re.I) and not re.search(
                r"\b(?:honey-flavou?red|artificial honey|honey candy)\b",name,re.I
            ):
                staple=(
                    "0409","natural honey, pre-packaged and labelled",
                    "Verify natural (not artificial/mixed) honey and pre-packaged-"
                    "and-labelled status from ingredients and supplier label."
                )
            elif re.search(r"\bcheese\b",name,re.I) and not re.search(
                r"\b(?:paneer|chena|cheese-flavou?red|cheese snack)\b",name,re.I
            ):
                staple=(
                    "0406","cheese other than paneer/chena",
                    "Verify dairy cheese and not paneer, chena, cheese-flavoured "
                    "snack or combined food preparation; supplier HSN/label needed."
                )
        if staple:
            hsn,kind,reason=staple
            candidate.update({
                "rate":"5",
                "hsnFamily":hsn,
                "confidence":"CONDITIONAL",
                "rule":f"2025 Schedule I grocery ({kind}): research rate 5%",
                "reason":reason+" No automatic GST classification approval.",
                "priceSensitive":False,
                "source":GOODS_RATE_SOURCE,
                "effectiveFrom":RATE_EFFECTIVE_DATE,
            })
            return candidate
    # Notification 9/2025 IGST Rate, Schedule II items 480, 490, 491,
    # and Schedule I item 484. Product type and tariff heading require
    # supplier model/packaging confirmation; all matches CONDITIONAL.
    # Exclude accessories, radio receiver combinations, imitation toys,
    # spare parts, unverified medical equipment and product bundles.
    if category=="Electronics":
        sub=str(product.get("subcategory") or "").casefold()
        electronic=None
        if (
            sub=="mobile phones"
            and re.search(
                r"\b(?:mobile\s+phone|keypad\s+phone|fold[\s-]?style\s+mobile|"
                r"mini\s+keypad\s+phone)\b",name,re.I
            )
            and not re.search(
                r"\b(?:cover|case|toy|dummy|replica|charger|"
                r"accessory|replacement|display\s+only|"
                r"screen\s+only|parts\s+only)\b",name,re.I
            )
        ):
            electronic=(
                "8517","18","complete cellular/mobile telephone handset",
                "Confirm working cellular telephone with SIM/network support, "
                "not a toy, imitation, spare part or accessory. Verify exact "
                "model, manufacturer label and supplier invoice HSN."
            )
        elif (
            sub=="power banks"
            and re.search(r"\bpower\s*bank\b",name,re.I)
            and not re.search(
                r"\b(?:cover|case|empty|housing|holder|"
                r"charger\s+only|replacement\s+cell|kit)\b",name,re.I
            )
        ):
            electronic=(
                "8507","18","complete rechargeable electric power bank",
                "Confirm integrated rechargeable lithium-ion accumulator, "
                "actual battery supplied and whether any charger or other "
                "goods are bundled; supplier classification HSN required."
            )
        elif (
            sub=="speakers & audio"
            and re.search(r"\b(?:portable\s+speaker|loudspeaker)\b",name,re.I)
            and not re.search(
                r"\b(?:radio|gramophone|record\s+player|"
                r"sound\s+system\s+set|toy|replica|"
                r"speaker\s+cover|spare|replacement|parts?\s+only|parts?)\b",name,re.I
            )
        ):
            electronic=(
                "8518","18","standalone loudspeaker with enclosure",
                "Verify sound reproduction through a working loudspeaker; "
                "exclude radio receiver/record player combinations, passive "
                "decorative imitation and separately bundled audio equipment."
            )
        elif (
            sub in ("massage guns","personal care appliances")
            and re.search(r"\b(?:massage\s+gun|handheld\s+massager|power\s+massager)\b",name,re.I)
            and not re.search(
                r"\b(?:oil|cream|massager\s+head\s+only|"
                r"replacement|case\s+only|toy|spare\s+part)\b",name,re.I
            )
        ):
            electronic=(
                "9019","5","complete mechanical massage apparatus",
                "Confirm an actual powered massage apparatus (not an "
                "accessory, replacement head or unrelated medical device), "
                "and verify product form/model and supplier HSN."
            )
        if electronic:
            hsn,rate,kind,reason=electronic
            candidate.update({
                "rate":rate,
                "hsnFamily":hsn,
                "confidence":"CONDITIONAL",
                "rule":f"2025 Schedule electrical goods ({kind}): research rate {rate}%",
                "reason":reason+" No automatic tax classification approval.",
                "priceSensitive":False,
                "source":GOODS_RATE_SOURCE,
                "effectiveFrom":RATE_EFFECTIVE_DATE,
            })
            return candidate
    # V12 owner declared plastic for exact current DIVNIX phone back-cover SKUs.
    # Heading 3926 is NOT approved for any product; actual finished goods,
    # particularly magnetic ring hybrids, require physical/tariff review.
    if (
        str(product.get("id") or "") in DIVNIX_OWNER_PLASTIC_COVER_V12_IDS
        and str(product.get("storeName") or "") == "DIVNIX TRENDY COVERS & ACCESSORIES"
        and re.search(r"\b(?:cover|case)\b", name, re.I)
        and not re.search(
            r"\b(?:screen\s+protector|glass\s+protector|camera\s+lens\s+protector|"
            r"tempered\s+glass|screen\s+guard|back\s+cover\s+replacement\s+part|"
            r"wallet|flip\s+case)\b",name,re.I
        )
    ):
        ring = str(product.get("id")) in DIVNIX_MAGNETIC_RING_V12_IDS
        review = (
            "Magnetic-ring cover: owner declares plastic casing, but ring/insert "
            "composition and finished composite article heading are unverified. "
            "Inspect the physical product and essential character before HSN."
            if ring else
            "Protective phone back cover: owner declares material 'plastic' "
            "without supplier evidence. Confirm the actual finished article "
            "is classifiable under heading 3926 rather than 4202, another "
            "heading, a handset part or a supplied bundle."
        )
        candidate.update({
            "rate":"18",
            "hsnFamily":"3926",
            "confidence":"CONDITIONAL",
            "rule":(
                "V12 owner-declared plastic DIVNIX mobile cover "
                + ("with magnetic ring" if ring else "back cover")
                + ": candidate 3926 / 18% (2025 Schedule II item 127)"
            ),
            "reason":review+" NO VERIFIED OR APPROVED TAX CLASSIFICATION. "
                     "No supplier HSN available; owner/accountant evidence review required.",
            "priceSensitive":False,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    # V13: exact 102 existing published Chapter 64 candidate SKUs.
    # Catalogue identifies category + footwear subcategory, but physical
    # pair and upper/sole material are NOT independently established.
    # Sale value threshold is the actual transaction value PER PAIR.
    if (
        str(product.get("id") or "") in FOOTWEAR_CATEGORY_V13_IDS
        and category=="Footwear"
        and str(product.get("subcategory") or "").strip()
        and not re.search(
            r"\b(?:polish|cream|wax|brush|lace|shoelace|"
            r"insole|spare|shoe\s+care|brace|"
            r"repair\s+kit|socks?|deodorizer|cleaner)\b",name,re.I
        )
    ):
        if price is None or price <= 0:
            candidate["reason"]=(
                "Footwear chapter 64 candidate: valid sale value missing; "
                "must confirm actual per-pair selling price, physical pair and materials."
            )
            return candidate
        candidate.update({
            "rate":"5" if price<=THRESHOLD else "18",
            "hsnFamily":"64",
            "confidence":"CONDITIONAL",
            "rule":"V13 footwear exact-SKU research: Chapter 64 <= Rs 2500 per pair 5%; above 18%",
            "reason":(
                "Product listed in Footwear with identifiable footwear subcategory. "
                "Confirm actual complete PAIR, sole/upper construction for 4-digit "
                "tariff heading (6401-6405), no accessory/brace/kit, and actual "
                "sale value per pair including discounts and quantity. "
                "Price changes may change GST research rate. No verified or "
                "approved HSN/GST classification; accountant review required."
            ),
            "priceSensitive":True,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    # Precise information requests instead of guessing GST from a broad category.
    # CBIC Notification 9/2025, Schedule II, serial 247 / heading 7007.
    # This is a conditional research match ONLY: phone screen protectors can
    # have adhesives, polymer films or composites and may not be 7007 goods.
    # Do not auto-approve, do not issue invoices and do not change product price.
    if category == "Electronics" and re.search(
        r"\btempered\s+glass\s+(?:screen|display)\s+protector\b",name,re.I
    ) and not re.search(
        r"\b(?:plastic|pet|hydrogel|tpu|film|liquid|privacy\s+film)\b",name,re.I
    ):
        candidate.update({
            "rate":"18",
            "hsnFamily":"7007",
            "confidence":"CONDITIONAL",
            "rule":"Heading 7007 toughened/tempered safety glass: 18%, Schedule II serial 247",
            "reason":(
                "Product title says tempered glass. Verify the actual glass "
                "construction, packaging and any composite/film material; "
                "only assign heading 7007 after product-specific check."
            ),
            "priceSensitive":False,
            "source":GOODS_RATE_SOURCE,
            "effectiveFrom":RATE_EFFECTIVE_DATE,
        })
        return candidate
    if category == "Electronics" and re.search(
        r"\b(?:tempered glass|screen protector|screen guard|lens protector)\b",name,re.I
    ):
        candidate["reason"]=(
            "Screen protector: verify actual glass/plastic/composite material, "
            "product packaging and tariff heading. Electronics category is not an HSN."
        )
    elif category == "Electronics" and re.search(
        r"\b(?:back cover|phone case|mobile cover|silicone case)\b",name,re.I
    ):
        candidate["reason"]=(
            "Mobile cover: verify TPU/silicone/polycarbonate/leather/composite "
            "material and correct tariff heading. No GST rate inferred."
        )
    elif category == "Groceries" and re.search(
        r"\b(?:rice|flour|atta|dal|pulses|wheat|grain|salt|spice)\b",name,re.I
    ):
        candidate["reason"]=(
            "Food grain/staple: verify pre-packaged-and-labelled status, "
            "package size, exact composition and exemption/rate notification."
        )
    elif category == "Accessories" and re.search(
        r"\b(?:bag|wallet|satchel|tote|purse|handbag|sling)\b",name,re.I
    ):
        candidate["reason"]=(
            "Bag/wallet: confirm outer surface material (leather, plastic, "
            "textile or other), construction and appropriate Chapter 42 heading."
        )
    elif category == "Beauty & Personal Care" and re.search(
        r"\b(?:conditioner|face serum|cleanser|lotion|sunscreen|balm)\b",name,re.I
    ):
        candidate["reason"]=(
            "Personal care: verify whether cosmetic, medicinal or other "
            "preparation and its actual notified HSN rate; do not assume shampoo's 5%."
        )
    return candidate


def high_confidence_records(
    products: list[dict[str,Any]], already_approved: list[dict[str,Any]]
) -> list[dict[str,str]]:
    """Propose only narrow, government-source-backed wristwatch approvals.

    No side effects; caller must require authenticated, explicit owner action
    before passing these records into audited approve_batch.
    """
    known={str(p.get("product_id")) for p in already_approved}
    rows=[]
    for product in products:
        if not isinstance(product,dict) or product.get("status")!="PUBLISHED":
            continue
        pid=str(product.get("id") or "")
        if not pid or pid in known:
            continue
        proposed=suggest(product)
        if proposed["confidence"]!="HIGH" or proposed["rate"]!="18":
            continue
        rows.append({
            "productId":pid,
            "hsnCode":"9102",   # Internal classification; hide on B2C PDF if eligible.
            "gstRate":"18",
            "supplyType":"taxable",
            "effectiveFrom":RATE_EFFECTIVE_DATE,
            "evidence":(
                "Government Notification No. 9/2025-Integrated Tax (Rate), "
                "Schedule II heading 9102, 18% conventional non-precious "
                "Casio F-91W/A158WA wristwatches. "+GOODS_RATE_SOURCE
            ),
        })
    return rows


def suggestion_coverage(products: list[dict[str,Any]]) -> dict[str,int]:
    counts={"HIGH":0,"CONDITIONAL":0,"UNCLASSIFIED":0}
    for p in products:
        if isinstance(p,dict) and p.get("status")=="PUBLISHED":
            counts[suggest(p)["confidence"]]+=1
    return {
        "sourceBackedWatchMatches":counts["HIGH"],
        "priceSensitiveRateSuggestions":counts["CONDITIONAL"],
        "needsFurtherClassification":counts["UNCLASSIFIED"],
    }


def _csv_cell(value: Any) -> str:
    value=str(value if value is not None else "").replace("\x00","").replace("\r"," ").replace("\n"," ")
    value=value[:1500]
    if value.lstrip().startswith(("=","+","-","@")):
        value="'"+value
    return value


def suggestions_csv(products: list[dict[str, Any]]) -> bytes:
    file=io.StringIO(newline="")
    writer=csv.DictWriter(file,fieldnames=EXPORT_FIELDS,lineterminator="\r\n")
    writer.writeheader()
    for p in products:
        if not isinstance(p,dict) or p.get("status")!="PUBLISHED":
            continue
        rate=suggest(p)
        writer.writerow({
            "productId":_csv_cell(p.get("id")),
            "productName":_csv_cell(p.get("name")),
            "category":_csv_cell(p.get("category")),
            "customerPrice":str(customer_price(p) or ""),
            "suggestedGstRate":rate["rate"] or "",
            "hsnFamily":rate["hsnFamily"],
            "effectiveFrom":rate["effectiveFrom"],
            "source":rate["source"],
            "rule":_csv_cell(rate["rule"]),
            "confidence":rate["confidence"],
            "reviewReason":_csv_cell(rate["reason"]),
            "priceSensitive":"YES" if rate["priceSensitive"] else "NO",
            "approval":"",  # Legal tax classification is not approved by downloading file.
        })
    return ("\ufeff"+file.getvalue()).encode("utf-8")
