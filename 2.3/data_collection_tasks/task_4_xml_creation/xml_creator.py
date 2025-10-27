# xml_creator.py
import xml.etree.ElementTree as ET

# Приклад даних (можна замінити або взяти з файлу)
unit_info = {
    "name": "1-а механізована бригада",
    "personnel": "3000",
    "status": "боєготова"
}

root = ET.Element("unit")
for k, v in unit_info.items():
    child = ET.SubElement(root, k)
    child.text = str(v)

tree = ET.ElementTree(root)
tree.write("unit_data.xml", encoding="utf-8", xml_declaration=True)
print("Створено unit_data.xml")
